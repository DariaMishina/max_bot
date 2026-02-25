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
"""
import asyncio
import logging

import aiomax
from aiomax import fsm, filters

from keyboards.main_menu import make_main_menu, make_back_to_menu_kb
from main.database import create_or_update_user, get_user_balance, can_user_divinate, create_user_balance, get_and_delete_webapp_follow_up_context
from main.conversions import save_conversion, save_paywall_conversion
from main.metrika_mp import generate_metrika_client_id, send_pageview, send_conversion_event

router = aiomax.Router()


@router.on_bot_start()
async def cmd_start(payload: aiomax.BotStartPayload, cursor: fsm.FSMCursor):
    """
    Обработка старта бота (аналог /start в Telegram).
    В Max мессенджере вызывается при первом обращении к боту.
    """
    logging.info(f"cmd_start: user_id={payload.user.user_id}, name={payload.user.name}")
    
    # Очищаем состояние
    cursor.clear()
    
    # Сохраняем/обновляем пользователя в БД
    try:
        is_new = await create_or_update_user(
            user_id=payload.user.user_id,
            username=payload.user.username,
            first_name=payload.user.name or "",
            last_name=None,
            language_code=None,
            is_premium=False,
        )
        if is_new:
            logging.info(f"New user registered: {payload.user.user_id}")
            
            # Сохраняем конверсию регистрации
            try:
                await save_conversion(
                    user_id=payload.user.user_id,
                    conversion_type='registration',
                    source='organic',
                )
            except Exception as e:
                logging.error(f"Error saving registration conversion: {e}", exc_info=True)
    except Exception as e:
        logging.error(f"Error saving user to database: {e}", exc_info=True)

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
