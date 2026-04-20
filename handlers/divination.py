"""
Обработчик гаданий — адаптировано для Max (aiomax).

Ключевые отличия от Telegram-версии:
- FSM через aiomax.fsm (строковые состояния, FSMCursor)
- Нет WebApp — для Таро используем кнопки CallbackButton для выбора карт
- message.sender.user_id вместо message.from_user.id
- bot.upload_image() вместо FSInputFile для отправки изображений
"""
import logging
import random
import re
import time
import aiohttp

import aiomax
from aiomax import fsm, filters, buttons

from keyboards.divination import make_divination_kb
from keyboards.main_menu import make_main_menu, make_back_to_menu_kb
from handlers.tarot_cards import (
    create_card_selection_keyboard, interpret_cards, get_card_image_path,
    get_all_available_cards, send_card_images, get_card_info, TAROT_CARDS,
    get_random_cards, combine_cards_image
)
from handlers.hexagrams import (
    get_all_available_hexagrams, get_hexagram_image_path,
    send_hexagram_image, get_hexagram_info, HEXAGRAMS
)
from main.database import can_user_divinate, use_divination, save_divination, get_user_balance, update_divination_interpretation, save_pending_question, get_and_delete_webapp_follow_up_context
from main.conversions import save_conversion, save_paywall_conversion
from main.metrika_mp import send_conversion_event

# Лимиты уточняющих вопросов после расклада
FOLLOW_UP_LIMIT_FREE = 2
FOLLOW_UP_LIMIT_PAID = 5

# FSM состояния (строковые для aiomax)
STATE_CHOOSING_DIVINATION = 'choosing_divination'
STATE_WAITING_FOR_QUESTION = 'waiting_for_question'
STATE_SELECTING_CARDS = 'selecting_cards'
STATE_CHATTING = 'chatting'

router = aiomax.Router()


# ==================== Команда /divination ====================

@router.on_command('divination')
async def cmd_divination(ctx: aiomax.CommandContext, cursor: fsm.FSMCursor):
    """Команда /divination - начинает новое гадание"""
    from handlers.common import check_channel_subscription, send_channel_sub_prompt
    user_id = ctx.sender.user_id
    logging.info(f"cmd_divination: user_id={user_id}")

    if not await check_channel_subscription(user_id):
        await send_channel_sub_prompt(ctx)
        return

    cursor.clear()
    
    await ctx.reply(
        "🔮 <b>Новое гадание</b>\n\n"
        "Напиши свой вопрос — о чём хочешь узнать?",
        keyboard=make_back_to_menu_kb(),
        format='html'
    )


# ==================== Свободный текстовый вопрос ====================
# В Max нет StatesGroup, поэтому ловим любой текст, который не является командой.
# Логика: если у пользователя нет активного состояния FSM,
# его текст считается вопросом для нового гадания.

@router.on_message(filters.state(STATE_CHOOSING_DIVINATION))
async def handle_divination_type_choice(message: aiomax.Message, cursor: fsm.FSMCursor):
    """Выбор типа гадания: Ицзин или Таро"""
    text = (message.content or "").strip()
    
    if text not in ["Ицзин", "Таро"]:
        await message.reply(
            "Пожалуйста, выберите тип гадания: Ицзин или Таро",
            keyboard=make_divination_kb()
        )
        return
    
    logging.info(f"Divination type chosen: {text} by user {message.sender.user_id}")
    
    data = cursor.get_data() or {}
    data['divination_type'] = text
    cursor.change_data(data)
    
    question = data.get('question')
    if question:
        # Вопрос уже есть — переходим к раскладу
        cursor.change_state(STATE_WAITING_FOR_QUESTION)
        await process_divination_internal(message, cursor, question)
    else:
        cursor.change_state(STATE_WAITING_FOR_QUESTION)
        if text == "Ицзин":
            await message.reply(
                "☯️ <b>Гадание по Ицзин</b>\n\n"
                "Задайте ваш вопрос о будущем, и я проведу гадание по древнекитайской Книге Перемен.",
                keyboard=make_back_to_menu_kb(),
                format='html'
            )
        else:
            await message.reply(
                "🃏 <b>Гадание на Таро</b>\n\n"
                "Задайте ваш вопрос, и я проведу гадание на картах Таро.",
                keyboard=make_back_to_menu_kb(),
                format='html'
            )


@router.on_message(filters.state(STATE_WAITING_FOR_QUESTION))
async def process_divination_question(message: aiomax.Message, cursor: fsm.FSMCursor):
    """Обработка вопроса для гадания"""
    text = (message.content or "").strip()
    
    if text.startswith("/"):
        if text == "/cancel":
            cursor.clear()
            await message.reply("❌ Гадание отменено.", keyboard=make_back_to_menu_kb())
        return
    
    if text in ["Ицзин", "Таро"]:
        await message.reply(
            "Пожалуйста, задайте ваш вопрос текстом.\n\n"
            "Например: «Что меня ждет в работе?» или «Стоит ли принимать это решение?»"
        )
        return
    
    await process_divination_internal(message, cursor, text)


async def process_divination_internal(message: aiomax.Message, cursor: fsm.FSMCursor, question: str):
    """Основная логика гадания"""
    user_id = message.sender.user_id
    logging.info(f"process_divination_internal: user_id={user_id}")
    
    # Проверяем баланс
    can_div, access_type = await can_user_divinate(user_id)
    if not can_div:
        try:
            data = cursor.get_data() or {}
            divination_type = data.get("divination_type", "неизвестно")
            await save_paywall_conversion(
                user_id=user_id,
                paywall_source="divination_blocked",
                metadata={'divination_type': divination_type, 'question': question[:100] if question else None}
            )
            import asyncio
            asyncio.create_task(send_conversion_event(user_id, 'paywall'))
        except Exception as e:
            logging.error(f"Error saving paywall conversion: {e}", exc_info=True)
        
        await message.reply(
            "❌ <b>У вас закончились гадания</b>\n\n"
            "Нажми ◀ В меню → Купить расклады 💎",
            keyboard=make_back_to_menu_kb(),
            format='html'
        )
        cursor.clear()
        return
    
    data = cursor.get_data() or {}
    divination_type = data.get("divination_type", "гадание")
    data['question'] = question
    cursor.change_data(data)
    
    if divination_type == "Ицзин":
        await _do_iching_divination(message, cursor, question, user_id)
    else:
        await _do_tarot_divination(message, cursor, question, user_id)


# ==================== Ицзин ====================

async def _do_iching_divination(message: aiomax.Message, cursor: fsm.FSMCursor, question: str, user_id: int):
    """Гадание по Ицзин"""
    from main.botdef import bot
    
    processing_msg = await message.reply("🔮 Провожу гадание...")
    
    try:
        all_hexagrams = get_all_available_hexagrams()
        random_hexagram_id = random.choice(all_hexagrams) if all_hexagrams else str(random.randint(1, 64))
        
        hexagram_info = get_hexagram_info(random_hexagram_id)
        hexagram_name = hexagram_info['name']
        hexagram_meaning = hexagram_info['meaning']
        
        # Отправляем изображение гексаграммы
        try:
            chat_id = message.recipient.chat_id
            await send_hexagram_image(bot, chat_id, random_hexagram_id)
        except Exception as e:
            logging.warning(f"Не удалось отправить изображение гексаграммы: {e}")
        
        # Редактируем сообщение о процессе
        try:
            await bot.edit_message(processing_msg.body.mid, text="🔮 Толкую гексаграмму...")
        except:
            pass
        
        # ChatGPT толкование
        system_prompt = (
            "Ты опытный гадатель по Ицзин (Книге Перемен). "
            "Проведи детальное и мистическое толкование гексаграммы по древнекитайской традиции. "
            "Проанализируй значение гексаграммы в контексте вопроса пользователя и дай целостную интерпретацию. "
            "Отвечай на русском языке, будь мудрым и проникновенным. "
            "Начни с краткого описания значения гексаграммы, затем дай детальное толкование в контексте вопроса."
        )
        chatgpt_question = (
            f"Вопрос пользователя: {question}\n\n"
            f"Выпавшая гексаграмма: {hexagram_name}\n"
            f"Значение гексаграммы: {hexagram_meaning}\n\n"
            "Дай детальное толкование этой гексаграммы Ицзин в контексте вопроса пользователя."
        )
        
        chatgpt_response = await get_chatgpt_response_with_prompt(chatgpt_question, system_prompt)
        
        # Списываем гадание
        balance_before = await get_user_balance(user_id)
        is_free = balance_before and balance_before['free_divinations_remaining'] > 0 if balance_before else True
        
        used = await use_divination(user_id)
        if not used:
            await message.reply("❌ Произошла ошибка при списании гадания.", keyboard=make_back_to_menu_kb())
            cursor.clear()
            return
        
        # Сохраняем в БД
        divination_id = await save_divination(
            user_id=user_id,
            divination_type="Ицзин",
            question=question,
            selected_cards=[random_hexagram_id],
            interpretation=chatgpt_response,
            is_free=is_free
        )
        
        if divination_id:
            try:
                await save_conversion(
                    user_id=user_id, conversion_type='service_usage',
                    divination_type="Ицзин",
                    metadata={'divination_id': divination_id, 'hexagram_id': random_hexagram_id, 'is_free': is_free}
                )
                import asyncio
                asyncio.create_task(send_conversion_event(user_id, 'service_usage'))
            except Exception as e:
                logging.error(f"Error saving conversion: {e}", exc_info=True)
        
        follow_up_limit = FOLLOW_UP_LIMIT_FREE if is_free else FOLLOW_UP_LIMIT_PAID
        conversation_history = [
            {"role": "user", "content": f"Мой вопрос: {question}"},
            {"role": "assistant", "content": chatgpt_response}
        ]
        
        data = cursor.get_data() or {}
        data.update({
            'divination_id': divination_id,
            'is_free_divination': is_free,
            'follow_up_count': 0,
            'conversation_history': conversation_history,
            'original_interpretation': chatgpt_response
        })
        cursor.change_data(data)
        
        await message.reply(
            f"☯️ <b>Результат гадания по Ицзин</b>\n\n"
            f"<b>Ваш вопрос:</b> <i>«{question}»</i>\n\n"
            f"<b>Выпавшая гексаграмма:</b> {hexagram_name}\n\n"
            f"<b>Толкование:</b>\n{chatgpt_response}\n\n"
            "💬 Хочешь уточнить расклад? Просто напиши свой вопрос.\n"
            "🔮 Новый расклад — нажми ◀ В меню",
            keyboard=make_back_to_menu_kb(),
            format='html'
        )
        
    except Exception as e:
        logging.error(f"Error in I-Ching divination: {e}", exc_info=True)
        await message.reply("❌ Произошла ошибка при гадании. Попробуйте позже.", keyboard=make_back_to_menu_kb())
        cursor.clear()
        return
    
    finally:
        try:
            await bot.delete_message(processing_msg.body.mid)
        except:
            pass
    
    cursor.change_state(STATE_CHATTING)


# ==================== Таро ====================

async def _do_tarot_divination(message: aiomax.Message, cursor: fsm.FSMCursor, question: str, user_id: int):
    """Гадание на Таро — случайный расклад или WebApp для выбора карт"""
    from main.botdef import bot as bot_instance

    await save_pending_question(user_id, question)

    kb = buttons.KeyboardBuilder()
    kb.row(buttons.CallbackButton("🔮 Карты покажут сами", "tarot_random"))

    try:
        me = await bot_instance.get_me()
        bot_ref = getattr(me, 'username', None) or getattr(me, 'user_id', None)
        if bot_ref:
            kb.row(buttons.WebAppButton("🃏 Выбрать карты самой", bot_ref))
    except Exception as e:
        logging.warning(f"Could not create WebAppButton: {e}")

    await message.reply(
        f"🃏 <b>Гадание на Таро</b>\n\n"
        f"Ваш вопрос: <i>«{question}»</i>\n\n"
        "Выберите способ гадания:\n"
        "• <b>🔮 Карты покажут сами</b> — случайный расклад\n"
        "• <b>🃏 Выбрать карты самой</b> — красивый интерфейс выбора",
        keyboard=kb,
        format='html'
    )
    cursor.change_state(STATE_SELECTING_CARDS)


@router.on_button_callback(lambda data: data.payload == 'tarot_random')
async def handle_tarot_random(cb: aiomax.Callback, cursor: fsm.FSMCursor):
    """Случайный расклад Таро"""
    from main.botdef import bot
    
    user_id = cb.user.user_id
    data = cursor.get_data() or {}
    question = data.get('question', '')
    
    if not question:
        await cb.answer("Пожалуйста, начните гадание заново.", text="Пожалуйста, начните гадание заново.", keyboard=[])
        cursor.clear()
        return
    
    await cb.answer("🔮 Тяну карты...", text="🔮 Тяну карты...", keyboard=[])
    
    try:
        # Выбираем 3 случайные карты
        card_ids = get_random_cards(3)
        
        # Отправляем изображения
        chat_id = cb.message.recipient.chat_id
        await send_card_images(bot, chat_id, card_ids, as_media_group=True)
        
        # ChatGPT толкование
        cards_info = []
        positions = ["Прошлое", "Настоящее", "Будущее"]
        for i, card_id in enumerate(card_ids):
            card = get_card_info(card_id)
            cards_info.append(f"{positions[i]}: {card['name']} — {card['meaning']}")
        
        system_prompt = (
            "Ты опытный таролог. Проведи детальное и мистическое толкование расклада из 3 карт Таро. "
            "Карты расположены: 1-я — Прошлое, 2-я — Настоящее, 3-я — Будущее. "
            "Проанализируй каждую карту в контексте вопроса пользователя и дай целостную интерпретацию. "
            "Отвечай на русском языке, будь мудрым и проникновенным. "
            "Начни с каждой карты отдельно, затем дай общее толкование."
        )
        chatgpt_question = (
            f"Вопрос пользователя: {question}\n\n"
            f"Выпавшие карты:\n" + "\n".join(cards_info) + "\n\n"
            "Дай детальное толкование этого расклада в контексте вопроса пользователя."
        )
        
        chatgpt_response = await get_chatgpt_response_with_prompt(chatgpt_question, system_prompt)
        
        # Списываем гадание
        balance_before = await get_user_balance(user_id)
        is_free = balance_before and balance_before['free_divinations_remaining'] > 0 if balance_before else True
        
        used = await use_divination(user_id)
        if not used:
            await bot.send_message("❌ Произошла ошибка при списании гадания.", chat_id=chat_id, keyboard=make_back_to_menu_kb())
            cursor.clear()
            return
        
        divination_id = await save_divination(
            user_id=user_id, divination_type="Таро", question=question,
            selected_cards=card_ids, interpretation=chatgpt_response, is_free=is_free
        )
        
        if divination_id:
            try:
                await save_conversion(
                    user_id=user_id, conversion_type='service_usage', divination_type="Таро",
                    metadata={'divination_id': divination_id, 'card_ids': card_ids, 'is_free': is_free}
                )
                import asyncio
                asyncio.create_task(send_conversion_event(user_id, 'service_usage'))
            except Exception as e:
                logging.error(f"Error saving conversion: {e}", exc_info=True)
        
        follow_up_limit = FOLLOW_UP_LIMIT_FREE if is_free else FOLLOW_UP_LIMIT_PAID
        conversation_history = [
            {"role": "user", "content": f"Мой вопрос: {question}"},
            {"role": "assistant", "content": chatgpt_response}
        ]
        
        data.update({
            'divination_id': divination_id, 'is_free_divination': is_free,
            'follow_up_count': 0, 'conversation_history': conversation_history,
            'original_interpretation': chatgpt_response
        })
        cursor.change_data(data)
        
        cards_names = [get_card_info(cid)['name'] for cid in card_ids]
        await bot.send_message(
            f"🃏 <b>Результат гадания на Таро</b>\n\n"
            f"<b>Ваш вопрос:</b> <i>«{question}»</i>\n\n"
            f"<b>Карты:</b> {', '.join(cards_names)}\n\n"
            f"<b>Толкование:</b>\n{chatgpt_response}\n\n"
            "💬 Хочешь уточнить расклад? Просто напиши свой вопрос.\n"
            "🔮 Новый расклад — нажми ◀ В меню",
            chat_id=chat_id,
            keyboard=make_back_to_menu_kb(),
            format='html'
        )
        
        cursor.change_state(STATE_CHATTING)
        
    except Exception as e:
        logging.error(f"Error in Tarot divination: {e}", exc_info=True)
        await bot.send_message(
            "❌ Произошла ошибка при гадании. Попробуйте ещё раз.",
            chat_id=cb.message.recipient.chat_id, keyboard=make_back_to_menu_kb()
        )
        cursor.clear()


@router.on_button_callback(lambda data: data.payload.startswith('select_card_'))
async def handle_card_selection(cb: aiomax.Callback, cursor: fsm.FSMCursor):
    """Обработка выбора карты"""
    card_id = cb.payload[len('select_card_'):]
    data = cursor.get_data() or {}
    selected = data.get('selected_cards', [])
    available = data.get('available_cards', [])
    
    if card_id in selected:
        selected.remove(card_id)
    elif len(selected) < 3:
        selected.append(card_id)
    else:
        await cb.answer("Уже выбрано 3 карты. Снимите одну, чтобы выбрать другую.")
        return
    
    data['selected_cards'] = selected
    cursor.change_data(data)
    
    kb = _build_card_selection_kb(available, selected)
    
    status = f"Выбрано {len(selected)}/3 карт"
    if len(selected) == 3:
        status += " — нажмите «Получить гадание»!"
    
    await cb.answer(status, keyboard=kb)


@router.on_button_callback(lambda data: data.payload == 'confirm_cards')
async def handle_confirm_cards(cb: aiomax.Callback, cursor: fsm.FSMCursor):
    """Подтверждение выбранных карт и получение гадания"""
    from main.botdef import bot
    
    data = cursor.get_data() or {}
    selected = data.get('selected_cards', [])
    question = data.get('question', '')
    user_id = cb.user.user_id
    chat_id = cb.message.recipient.chat_id
    
    if len(selected) != 3:
        await cb.answer("Необходимо выбрать ровно 3 карты!")
        return
    
    await cb.answer("🔮 Толкую карты...")
    
    try:
        # Отправляем изображения
        await send_card_images(bot, chat_id, selected, as_media_group=True)
        
        # ChatGPT
        cards_info = []
        positions = ["Прошлое", "Настоящее", "Будущее"]
        for i, card_id in enumerate(selected):
            card = get_card_info(card_id)
            cards_info.append(f"{positions[i]}: {card['name']} — {card['meaning']}")
        
        system_prompt = (
            "Ты опытный таролог. Проведи детальное и мистическое толкование расклада из 3 карт Таро. "
            "Карты расположены: 1-я — Прошлое, 2-я — Настоящее, 3-я — Будущее. "
            "Проанализируй каждую карту в контексте вопроса пользователя и дай целостную интерпретацию. "
            "Отвечай на русском языке, будь мудрым и проникновенным."
        )
        chatgpt_question = (
            f"Вопрос пользователя: {question}\n\n"
            f"Выпавшие карты:\n" + "\n".join(cards_info) + "\n\n"
            "Дай детальное толкование этого расклада в контексте вопроса пользователя."
        )
        
        chatgpt_response = await get_chatgpt_response_with_prompt(chatgpt_question, system_prompt)
        
        balance_before = await get_user_balance(user_id)
        is_free = balance_before and balance_before['free_divinations_remaining'] > 0 if balance_before else True
        
        used = await use_divination(user_id)
        if not used:
            await bot.send_message("❌ Ошибка при списании гадания.", chat_id=chat_id, keyboard=make_back_to_menu_kb())
            cursor.clear()
            return
        
        divination_id = await save_divination(
            user_id=user_id, divination_type="Таро", question=question,
            selected_cards=selected, interpretation=chatgpt_response, is_free=is_free
        )
        
        if divination_id:
            try:
                await save_conversion(
                    user_id=user_id, conversion_type='service_usage', divination_type="Таро",
                    metadata={'divination_id': divination_id, 'card_ids': selected, 'is_free': is_free, 'method': 'manual'}
                )
                import asyncio
                asyncio.create_task(send_conversion_event(user_id, 'service_usage'))
            except Exception as e:
                logging.error(f"Error saving conversion: {e}", exc_info=True)
        
        conversation_history = [
            {"role": "user", "content": f"Мой вопрос: {question}"},
            {"role": "assistant", "content": chatgpt_response}
        ]
        data.update({
            'divination_id': divination_id, 'is_free_divination': is_free,
            'follow_up_count': 0, 'conversation_history': conversation_history,
            'original_interpretation': chatgpt_response
        })
        cursor.change_data(data)
        
        cards_names = [get_card_info(cid)['name'] for cid in selected]
        await bot.send_message(
            f"🃏 <b>Результат гадания на Таро</b>\n\n"
            f"<b>Ваш вопрос:</b> <i>«{question}»</i>\n\n"
            f"<b>Карты:</b> {', '.join(cards_names)}\n\n"
            f"<b>Толкование:</b>\n{chatgpt_response}\n\n"
            "💬 Хочешь уточнить расклад? Просто напиши свой вопрос.\n"
            "🔮 Новый расклад — нажми ◀ В меню",
            chat_id=chat_id, keyboard=make_back_to_menu_kb(), format='html'
        )
        
        cursor.change_state(STATE_CHATTING)
        
    except Exception as e:
        logging.error(f"Error in manual Tarot divination: {e}", exc_info=True)
        await bot.send_message("❌ Ошибка при гадании. Попробуйте ещё раз.", chat_id=chat_id, keyboard=make_back_to_menu_kb())
        cursor.clear()


@router.on_button_callback(lambda data: data.payload == 'cancel_cards')
async def handle_cancel_cards(cb: aiomax.Callback, cursor: fsm.FSMCursor):
    """Отмена выбора карт"""
    cursor.clear()
    await cb.answer("❌ Гадание отменено.")


# ==================== Уточняющие вопросы (chatting) ====================

async def _process_follow_up_message(message: aiomax.Message, cursor: fsm.FSMCursor):
    """
    Обработать одно сообщение как уточняющий вопрос по раскладу.
    Используется из handle_follow_up и при первом уточнении после WebApp-гадания.
    """
    text = (message.content or "").strip()
    
    if text.startswith("/"):
        if text == "/cancel":
            cursor.clear()
            await message.reply("Вы вернулись в главное меню.", keyboard=make_back_to_menu_kb())
        return
    
    data = cursor.get_data() or {}
    follow_up_count = data.get('follow_up_count', 0)
    is_free = data.get('is_free_divination', True)
    follow_up_limit = FOLLOW_UP_LIMIT_FREE if is_free else FOLLOW_UP_LIMIT_PAID
    
    if follow_up_count >= follow_up_limit:
        await message.reply(
            f"💬 Лимит уточняющих вопросов ({follow_up_limit}) исчерпан.\n\n"
            "Нажми ◀ В меню, чтобы начать новый расклад или купить дополнительные.",
            keyboard=make_back_to_menu_kb()
        )
        cursor.clear()
        return
    
    conversation_history = data.get('conversation_history', [])
    conversation_history.append({"role": "user", "content": text})
    
    system_prompt = (
        "Ты опытный гадатель и таролог. "
        "Пользователь задает уточняющий вопрос по уже проведенному раскладу. "
        "Отвечай на русском, будь мудрым и проникновенным. "
        "Используй контекст предыдущего расклада для ответа."
    )
    
    try:
        response = await get_chatgpt_response_with_history(conversation_history, system_prompt)
        
        conversation_history.append({"role": "assistant", "content": response})
        data['conversation_history'] = conversation_history
        data['follow_up_count'] = follow_up_count + 1
        cursor.change_data(data)
        
        remaining = follow_up_limit - follow_up_count - 1
        if remaining > 0:
            footer = f"\n\n💬 Осталось уточняющих вопросов: {remaining}"
        else:
            footer = "\n\n⚠️ Это был последний уточняющий вопрос по раскладу."
        
        await message.reply(response + footer, keyboard=make_back_to_menu_kb(), format='html')
        
        divination_id = data.get('divination_id')
        if divination_id:
            full_interpretation = data.get('original_interpretation', '') + f"\n\n---\n💬 Уточнение: {text}\n{response}"
            await update_divination_interpretation(divination_id, full_interpretation)
        
    except Exception as e:
        logging.error(f"Error in follow-up question: {e}", exc_info=True)
        await message.reply("❌ Ошибка при обработке вопроса. Попробуйте ещё раз.", keyboard=make_back_to_menu_kb())


@router.on_message(filters.state(STATE_CHATTING))
async def handle_follow_up(message: aiomax.Message, cursor: fsm.FSMCursor):
    """Обработка уточняющих вопросов после расклада"""
    await _process_follow_up_message(message, cursor)


# ==================== Свободный текст как новый вопрос ====================

@router.on_message()
async def handle_free_text_question(message: aiomax.Message, cursor: fsm.FSMCursor):
    """
    Ловит любой текст без активного состояния FSM — считает его вопросом для нового гадания.
    Если есть сохранённый контекст после WebApp-гадания — обрабатывает как уточняющий вопрос.
    """
    text = (message.content or "").strip()
    
    if not text or text.startswith("/"):
        return
    
    if text in ["Мои гадания 🔮", "Новый расклад 🃏", "Купить расклады 💎", "Карта дня ✨", "Личная консультация 🔮"]:
        return
    
    if cursor.get_state() is not None:
        return
    
    user_id = message.sender.user_id
    
    # Уточняющий вопрос после WebApp-гадания (контекст в БД, т.к. FSM недоступен из HTTP)
    ctx = await get_and_delete_webapp_follow_up_context(user_id)
    if ctx is not None:
        cursor.change_data(ctx)
        cursor.change_state(STATE_CHATTING)
        await _process_follow_up_message(message, cursor)
        return
    
    # Проверяем подписку на канал (для новых пользователей)
    from handlers.common import check_channel_subscription, send_channel_sub_prompt
    if not await check_channel_subscription(user_id):
        await send_channel_sub_prompt(message)
        return

    logging.info(f"Free text question from user {user_id}: {text[:50]}")
    
    # Сохраняем вопрос и предлагаем выбрать тип гадания
    cursor.change_data({'question': text})
    cursor.change_state(STATE_CHOOSING_DIVINATION)
    
    await message.reply(
        f"🔮 Ваш вопрос: <i>«{text}»</i>\n\n"
        "Выберите тип гадания:",
        keyboard=make_divination_kb(),
        format='html'
    )


# ==================== Утилиты ====================

def _build_card_selection_kb(available: list, selected: list) -> buttons.KeyboardBuilder:
    """Построить клавиатуру выбора карт"""
    kb = buttons.KeyboardBuilder()
    for card_id in available:
        card_info = get_card_info(card_id)
        if card_id in selected:
            text = f"✅ {card_info['name']}"
        else:
            text = f"🃏 {card_info['name']}"
        kb.row(buttons.CallbackButton(text, f"select_card_{card_id}"))
    
    if len(selected) == 3:
        kb.row(buttons.CallbackButton("🔮 Получить гадание", "confirm_cards", intent='positive'))
    
    kb.row(buttons.CallbackButton("❌ Отмена", "cancel_cards", intent='negative'))
    return kb


def format_interpretation_with_bold(text: str) -> str:
    """Форматирует текст толкования, выделяя жирным ключевые слова"""
    keywords = ["Прошлое", "Настоящее", "Будущее", "Общее толкование"]
    
    formatted_text = text
    
    for keyword in keywords:
        markdown_pattern = rf'(^|\n)\s*###\s*({re.escape(keyword)})(\s*:)'
        markdown_replacement = r'\1<b>\2</b>\3'
        formatted_text = re.sub(markdown_pattern, markdown_replacement, formatted_text, flags=re.IGNORECASE | re.MULTILINE)
        
        markdown_bold_pattern = rf'\*\*({re.escape(keyword)})\*\*(\s*:)'
        markdown_bold_replacement = r'<b>\1</b>\2'
        formatted_text = re.sub(markdown_bold_pattern, markdown_bold_replacement, formatted_text, flags=re.IGNORECASE)
    
    for keyword in keywords:
        if re.search(rf'<b>\s*{re.escape(keyword)}\s*</b>', formatted_text, re.IGNORECASE):
            continue
        pattern = rf'(^|\n)({re.escape(keyword)})(\s*:)'
        replacement = r'\1<b>\2</b>\3'
        formatted_text = re.sub(pattern, replacement, formatted_text, flags=re.IGNORECASE | re.MULTILINE)
    
    return formatted_text


async def get_chatgpt_response_with_prompt(question: str, system_prompt: str) -> str:
    """Отправка запроса к ChatGPT API с кастомным системным промптом"""
    from main.config_reader import config
    
    api_key = config.api_key.get_secret_value()
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        "max_tokens": 1000,
        "temperature": 0.8
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                result = await response.json()
                response_text = result["choices"][0]["message"]["content"]
                return format_interpretation_with_bold(response_text)
            else:
                error_text = await response.text()
                logging.error(f"ChatGPT API error: {response.status} - {error_text}")
                raise Exception(f"Ошибка API: {response.status}")


async def get_chatgpt_response_with_history(messages: list, system_prompt: str) -> str:
    """Отправка запроса к ChatGPT API с историей диалога"""
    from main.config_reader import config
    
    api_key = config.api_key.get_secret_value()
    
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    all_messages = [{"role": "system", "content": system_prompt}] + messages
    
    data = {
        "model": "gpt-4o-mini",
        "messages": all_messages,
        "max_tokens": 1000,
        "temperature": 0.8
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                result = await response.json()
                response_text = result["choices"][0]["message"]["content"]
                return format_interpretation_with_bold(response_text)
            else:
                error_text = await response.text()
                logging.error(f"ChatGPT API error: {response.status} - {error_text}")
                raise Exception(f"Ошибка API: {response.status}")
