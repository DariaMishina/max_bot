"""
Общие обработчики: /start (on_bot_start), /balance, неизвестные команды.
Адаптировано с aiogram на aiomax.

Ключевые отличия от Telegram-версии:
- on_bot_start() вместо Command("start")
- message.sender.user_id вместо message.from_user.id
- message.sender.name вместо message.from_user.full_name
- message.sender.username вместо message.from_user.username
- message.reply(text) / message.send(text) вместо message.answer(text)
- FSMCursor вместо FSMContext с StatesGroup
- keyboard=kb вместо reply_markup=kb

Кампания Директ → лендинг → бот: start-параметр с лендинга в формате
__client_id__XXX__camp_YYY (client_id Метрики и utm_campaign) парсится и сохраняется в БД.
"""
import asyncio
import logging
from typing import Optional, Tuple

import aiomax
from aiomax import fsm, filters, buttons

from keyboards.main_menu import make_main_menu, make_back_to_menu_kb
from main.database import (
    create_or_update_user, get_user_balance, can_user_divinate,
    create_user_balance, get_and_delete_webapp_follow_up_context,
    has_paid_access, mark_channel_subscribed, clear_channel_subscribed,
)
from main.conversions import save_conversion, save_paywall_conversion
from main.metrika_mp import generate_metrika_client_id, send_pageview, send_conversion_event
from main.config_reader import config

router = aiomax.Router()


def _parse_start_param_from_landing(start_param: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Парсит start-параметр с лендинга (формат как в TG: __client_id__XXX__camp_YYY).
    Возвращает (client_id, utm_campaign).
    """
    if not start_param or not isinstance(start_param, str):
        return None, None
    s = start_param.strip()
    if not s or "__client_id__" not in s:
        return None, None
    parts = s.split("__client_id__")
    if len(parts) < 2:
        return None, None
    client_id_part = parts[1]
    client_id = None
    utm_campaign = None
    if "__" in client_id_part:
        segs = client_id_part.split("__")
        client_id = segs[0] if segs else None
        for seg in segs[1:]:
            if seg.startswith("camp_"):
                utm_campaign = seg[5:]
                break
    else:
        client_id = client_id_part
    return client_id or None, utm_campaign or None


# ==================== Проверка подписки на канал ====================

def _make_channel_sub_kb() -> buttons.KeyboardBuilder:
    """Клавиатура с кнопками «Подписаться» и «Проверить подписку»."""
    kb = buttons.KeyboardBuilder()
    if config.channel_url:
        kb.row(buttons.LinkButton("📢 Подписаться на канал", config.channel_url))
    kb.row(buttons.CallbackButton("✅ Подписка оформлена", "check_channel_sub"))
    return kb


CHANNEL_SUB_TEXT = (
    '📢 <b>Для использования бота подпишись на наш '
    '<a href="{url}">канал</a>:</b>\n\n'
    "После подписки нажми кнопку ниже 👇"
)


async def check_channel_subscription(user_id: int) -> bool:
    """
    Проверить, нужно ли блокировать пользователя из-за отсутствия подписки на канал.
    Возвращает True если пользователь может продолжать, False если нужно показать гейт.

    Платящие пользователи (безлимит / платные гадания) — проверка пропускается.
    Остальные — проверяются через MAX API при каждом обращении.
    """
    if not config.channel_chat_id:
        return True

    if await has_paid_access(user_id):
        return True

    from main.botdef import bot
    try:
        member = await bot.get_memberships(config.channel_chat_id, user_id)
        if member is not None:
            await mark_channel_subscribed(user_id)
            return True
        else:
            await clear_channel_subscribed(user_id)
    except Exception as e:
        logging.error(f"Error checking channel membership for user {user_id}: {e}", exc_info=True)
        return True  # fail open

    return False


async def send_channel_sub_prompt(msg) -> None:
    """Отправить сообщение с просьбой подписаться на канал."""
    url = config.channel_url or "канал"
    text = CHANNEL_SUB_TEXT.format(url=url)
    if hasattr(msg, 'reply'):
        await msg.reply(text, keyboard=_make_channel_sub_kb(), format='html')
    else:
        await msg.send(text, keyboard=_make_channel_sub_kb(), format='html')


@router.on_button_callback(lambda data: data.payload == 'check_channel_sub')
async def handle_check_channel_sub(cb: aiomax.Callback, cursor: fsm.FSMCursor):
    """Кнопка «Я подписалась» — повторно проверяем подписку на канал через API."""
    user_id = cb.user.user_id

    if not config.channel_chat_id:
        await cb.answer("Проверка подписки не настроена.")
        return

    from main.botdef import bot
    try:
        member = await bot.get_memberships(config.channel_chat_id, user_id)
    except Exception as e:
        logging.error(f"Error checking channel membership on callback for {user_id}: {e}", exc_info=True)
        await cb.answer("Произошла ошибка, попробуй ещё раз.")
        return

    if member is not None:
        await mark_channel_subscribed(user_id)
        await cb.send(
            "🎉 <b>Отлично, подписка подтверждена!</b>\n\n"
            "Теперь напиши свой вопрос в чат 🔮",
            keyboard=make_main_menu(),
            format='html',
        )
    else:
        url = config.channel_url or "канал"
        await cb.send(
            "❌ Подписка на канал не найдена.\n\n"
            f'Подпишись на <a href="{url}">канал</a> '
            "и нажми кнопку ещё раз 👇",
            keyboard=_make_channel_sub_kb(),
            format='html',
        )


@router.on_bot_start()
async def cmd_start(payload: aiomax.BotStartPayload, cursor: fsm.FSMCursor):
    """
    Обработка старта бота (аналог /start в Telegram).
    В Max мессенджере вызывается при первом обращении к боту.
    Поддерживается start-параметр с лендинга: __client_id__XXX__camp_YYY.
    """
    # В aiomax start-параметр из URL (?start=XXX) приходит в BotStartPayload.payload
    start_param = payload.payload
    logging.info(f"cmd_start: user_id={payload.user.user_id}, name={payload.user.name}, start_param={start_param!r}")

    client_id = None
    utm_campaign = None
    if start_param:
        client_id, utm_campaign = _parse_start_param_from_landing(start_param)
        if client_id:
            logging.info(f"Parsed landing start param: client_id={client_id}, utm_campaign={utm_campaign}")

    # Очищаем состояние
    cursor.clear()

    source = "landing" if client_id else "organic"
    if client_id and not utm_campaign:
        utm_campaign = None

    # Сохраняем/обновляем пользователя в БД
    is_new = False
    try:
        is_new = await create_or_update_user(
            user_id=payload.user.user_id,
            username=payload.user.username,
            first_name=payload.user.name or "",
            last_name=None,
            language_code=None,
            is_premium=False,
            client_id=client_id,
            utm_source="landing" if client_id else None,
            utm_campaign=utm_campaign,
        )
        if is_new:
            logging.info(f"New user registered: {payload.user.user_id} with source={source}")

            # Сохраняем конверсию регистрации
            try:
                await save_conversion(
                    user_id=payload.user.user_id,
                    conversion_type="registration",
                    source=source,
                    client_id=client_id,
                    campaign_id=utm_campaign,
                )
            except Exception as e:
                logging.error(f"Error saving registration conversion: {e}", exc_info=True)
    except Exception as e:
        logging.error(f"Error saving user to database: {e}", exc_info=True)

    is_subscribed = await check_channel_subscription(payload.user.user_id)

    if is_new and not is_subscribed:
        await payload.send(
            "🪬 Тревожно? Не знаешь, как поступить?\n\n"
            "Не с кем посоветоваться, а онлайн-расклады — пустые слова.\n\n"
            "🕯 Сделай расклад — и получи мгновенное толкование Таро и И-Цзин с помощью ИИ.\n\n"
            "📌 Как работает:\n\n"
            "1️⃣ Пишешь свой вопрос\n"
            "2️⃣ Выбираешь тип гадания — Таро или И-Цзин\n"
            "3️⃣ Бот выдает карты или гексаграмму\n"
            "💬 Бот сразу покажет толкование и комментарий именно под твой вопрос.\n\n"
            '<b>📢 Чтобы начать — подпишись на наш '
            f'<a href="{config.channel_url}">канал</a> и нажми кнопку ниже 👇</b>',
            keyboard=_make_channel_sub_kb(),
            format='html',
        )
    else:
        await payload.send(
            "🪬 Тревожно? Не знаешь, как поступить?\n\n"
            "Не с кем посоветоваться, а онлайн-расклады — пустые слова.\n\n"
            "🕯 Сделай расклад — и получи мгновенное толкование Таро и И-Цзин с помощью ИИ.\n\n"
            "📌 Как работает:\n\n"
            "1️⃣ Пишешь свой вопрос\n"
            "2️⃣ Выбираешь тип гадания — Таро или И-Цзин\n"
            "3️⃣ Бот выдает карты или гексаграмму\n"
            "💬 Бот сразу покажет толкование и комментарий именно под твой вопрос.\n\n"
            "<b>💫 Чтобы начать — напиши свой вопрос в чат. У тебя есть 3 бесплатных гадания 👇</b>",
            keyboard=make_main_menu(),
            format='html',
        )


@router.on_command('balance')
async def show_balance_cmd(ctx: aiomax.CommandContext, cursor: fsm.FSMCursor):
    """Показать баланс по команде /balance"""
    await _show_balance(ctx, cursor)


@router.on_message(filters.equals("Мои гадания 🔮"))
async def show_balance_button(message: aiomax.Message, cursor: fsm.FSMCursor):
    """Показать баланс по кнопке «Мои гадания 🔮»"""
    await _show_balance(message, cursor)


@router.on_message(filters.equals("Новый расклад 🃏"))
async def new_divination_button(message: aiomax.Message, cursor: fsm.FSMCursor):
    """Кнопка «Новый расклад 🃏» — просит ввести вопрос"""
    cursor.clear()
    await message.reply(
        "🔮 Напиши свой вопрос — о чём хочешь узнать?",
        keyboard=make_back_to_menu_kb()
    )


@router.on_message(filters.equals("Купить расклады 💎"))
async def buy_button(message: aiomax.Message, cursor: fsm.FSMCursor):
    """Кнопка «Купить расклады 💎» — переходит в оплату"""
    from handlers.pay import cmd_pay_internal
    cursor.clear()
    await cmd_pay_internal(message)


@router.on_message(filters.equals("Личная консультация 🔮"))
async def consultation_menu_button(message: aiomax.Message, cursor: fsm.FSMCursor):
    """Кнопка «Личная консультация 🔮» — описание услуги и 2 тарифа."""
    from keyboards.pay import make_consultation_kb
    cursor.clear()
    user_id = message.sender.user_id
    logging.info(f"consultation_menu: user_id={user_id}")

    try:
        await save_paywall_conversion(user_id=user_id, paywall_source="menu_consultation")
        asyncio.create_task(send_conversion_event(user_id, 'paywall'))
    except Exception as e:
        logging.error(f"Error saving paywall conversion (consultation): {e}", exc_info=True)

    tarologist_name = config.tarologist_name or "Диана"
    work_hours = config.tarologist_work_hours or "10:00–22:00"
    await message.reply(
        f"🔮 <b>Личная консультация с тарологом {tarologist_name}</b>\n\n"
        f"Получи разбор от живого таролога — не алгоритм, а человек с опытом.\n"
        f"{tarologist_name} ответит лично в течение часа в рабочие часы "
        f"({work_hours} МСК).\n\n"
        f"✨ <b>Базовый разбор — 500₽</b>\n"
        f"Расклад на один вопрос. Карты трактуются вместе — целостная "
        f"картина ситуации и конкретный совет. Коротко и по делу.\n\n"
        f"🔮 <b>Подробный разбор — 1500₽</b> (оптимально для большинства ситуаций)\n"
        f"— что происходит сейчас\n"
        f"— скрытые моменты\n"
        f"— к чему всё идёт\n"
        f"— совет от карт",
        keyboard=make_consultation_kb(),
        format='html'
    )


@router.on_message(filters.equals("Карта дня ✨"))
async def daily_card_button(message: aiomax.Message, cursor: fsm.FSMCursor):
    """Кнопка «Карта дня ✨» — показать выбор карты дня"""
    from handlers.daily_card import create_daily_card_keyboard
    cursor.clear()
    user_id = message.sender.user_id
    kb = await create_daily_card_keyboard(user_id)
    await message.reply(
        "🃏 <b>Выбери свою карту дня</b>\n\n"
        "Нажми на одну из карт, чтобы узнать послание дня ✨",
        keyboard=kb,
        format='html'
    )


@router.on_button_callback(lambda data: data.payload == 'back_to_menu')
async def handle_back_to_menu(cb: aiomax.Callback, cursor: fsm.FSMCursor):
    """Кнопка «◀ В меню» — показывает полное меню и сбрасывает контекст уточнений WebApp."""
    cursor.clear()
    user_id = cb.user.user_id
    await get_and_delete_webapp_follow_up_context(user_id)
    await cb.send(
        "🪬 Выбери действие или просто напиши свой вопрос в чат 👇",
        keyboard=make_main_menu()
    )


async def _show_balance(msg, cursor: fsm.FSMCursor):
    """
    Внутренняя функция: показывает остаток гаданий из БД.
    msg может быть Message или CommandContext.
    """
    user_id = msg.sender.user_id if hasattr(msg, 'sender') else msg.user.user_id
    user_name = msg.sender.name if hasattr(msg, 'sender') else msg.user.name
    logging.info(f"show_balance: user_id={user_id}")
    
    try:
        balance = await get_user_balance(user_id)
        if balance:
            free_remaining = balance['free_divinations_remaining']
            paid_remaining = balance['paid_divinations_remaining']
            unlimited_until = balance['unlimited_until']
            total_used = balance['total_divinations_used']
            
            balance_text = "🔮 <b>Ваш баланс гаданий</b>\n\n"
            
            if unlimited_until:
                from datetime import datetime
                if unlimited_until > datetime.now():
                    balance_text += f"👑 <b>Безлимит активен до</b> {unlimited_until.strftime('%d.%m.%Y %H:%M')}\n\n"
                else:
                    balance_text += f"👑 Безлимит истек\n\n"
            
            balance_text += f"🆓 Бесплатных гаданий: <b>{free_remaining}</b>\n"
            balance_text += f"💎 Платных гаданий: <b>{paid_remaining}</b>\n"
            balance_text += f"📊 Всего использовано: <b>{total_used}</b>\n\n"
            
            can_divinate, access_type = await can_user_divinate(user_id)
            if not can_divinate:
                balance_text += "Гадания закончились — нажми ◀ В меню → Купить расклады 💎"
                
                try:
                    await save_paywall_conversion(
                        user_id=user_id,
                        paywall_source="balance_view",
                        metadata={
                            'free_remaining': free_remaining,
                            'paid_remaining': paid_remaining,
                            'total_used': total_used,
                            'access_type': access_type,
                        }
                    )
                    asyncio.create_task(send_conversion_event(user_id, 'paywall'))
                except Exception as e:
                    logging.error(f"Error saving paywall conversion: {e}", exc_info=True)
            else:
                balance_text += "Можешь начинать гадать! Просто напиши свой вопрос в чат."
            
            if hasattr(msg, 'reply'):
                await msg.reply(balance_text, keyboard=make_back_to_menu_kb(), format='html')
            else:
                await msg.send(balance_text, keyboard=make_back_to_menu_kb(), format='html')
        else:
            await create_user_balance(user_id)
            text = (
                "🔮 <b>Ваш баланс гаданий</b>\n\n"
                "У вас осталось <b>3 бесплатных гадания</b>\n\n"
                "Гадания закончились — нажми ◀ В меню → Купить расклады 💎"
            )
            if hasattr(msg, 'reply'):
                await msg.reply(text, keyboard=make_back_to_menu_kb(), format='html')
            else:
                await msg.send(text, keyboard=make_back_to_menu_kb(), format='html')
    except Exception as e:
        logging.error(f"Error getting balance: {e}", exc_info=True)
        text = (
            "🔮 <b>Ваш баланс гаданий</b>\n\n"
            "Произошла ошибка при получении баланса. Попробуйте позже."
        )
        if hasattr(msg, 'reply'):
            await msg.reply(text, keyboard=make_back_to_menu_kb(), format='html')
        else:
            await msg.send(text, keyboard=make_back_to_menu_kb(), format='html')
