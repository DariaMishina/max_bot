"""
Обработчик оплаты — адаптировано для Max (aiomax).

Используем ЮKassa API для создания платежей.
В Max нет встроенных платежей как в Telegram, поэтому
используем исключительно внешние ссылки на оплату через ЮKassa.

Ключевые отличия:
- FSM через строковые состояния (aiomax.fsm)
- CallbackButton вместо ReplyKeyboardMarkup
- LinkButton для ссылки на оплату
"""
import logging
import re
import json
import uuid
import base64
import aiohttp
import time

import aiomax
from aiomax import fsm, filters, buttons

from keyboards.pay import make_payment_kb, make_email_confirmation_kb
from keyboards.main_menu import make_main_menu, make_back_to_menu_kb
from main.botdef import bot
from main.config_reader import config
from main.database import (
    create_payment, process_successful_payment as db_process_successful_payment,
    update_payment_status, update_user_email, get_user_email, get_latest_pending_payment
)
from main.conversions import save_conversion, save_paywall_conversion
from main.metrika_mp import send_conversion_event

router = aiomax.Router()

# FSM состояния
STATE_WAITING_EMAIL = 'waiting_for_email'
STATE_CONFIRMING_EMAIL = 'confirming_email'
STATE_WAITING_PAYMENT = 'waiting_for_payment'

# Пакеты оплаты
PACKAGES = {
    'pay_3_spreads': {'id': '3_spreads', 'name': '3 расклада', 'amount': 6900, 'amount_rub': 69.0, 'divinations': 3},
    'pay_10_spreads': {'id': '10_spreads', 'name': '10 раскладов', 'amount': 14900, 'amount_rub': 149.0, 'divinations': 10},
    'pay_20_spreads': {'id': '20_spreads', 'name': '20 раскладов', 'amount': 24900, 'amount_rub': 249.0, 'divinations': 20},
    'pay_30_spreads': {'id': '30_spreads', 'name': '30 раскладов', 'amount': 34900, 'amount_rub': 349.0, 'divinations': 30},
    'pay_unlimited': {'id': 'unlimited', 'name': 'Безлимит на месяц', 'amount': 49900, 'amount_rub': 499.0, 'divinations': -1},
}
PAYMENT_PACKAGES = PACKAGES
# Для webhook: поиск пакета по id из metadata (там приходит '3_spreads', а не 'pay_3_spreads')
PACKAGES_BY_ID = {p['id']: p for p in PACKAGES.values()}


_PAY_TEXT = (
    "💎 <b>Бесплатные гадания закончились</b>\n\n"
    "Ты уже почувствовала, как это работает — бот даёт точные расклады прямо здесь и сейчас.\n\n"
    "✨ <b>Хочешь продолжить гадать, когда нужен ответ?</b>\n"
    "Перед встречей, в отношениях, когда тревожно — бот всегда с тобой.\n\n"
    "<b>🔥 Самый популярный вариант</b>\n"
    "👑 Безлимит на месяц — 499₽\n"
    "Гадай когда угодно и сколько угодно. Полная анонимность.\n\n"
    "Или выбери пакет:\n"
    "🔥 30 раскладов — 349₽\n"
    "🌟 20 раскладов — 249₽\n"
    "💫 10 раскладов — 149₽\n"
    "🌙 3 расклада — 69₽"
)


async def cmd_pay_internal(msg):
    """Общая логика показа меню оплаты (вызывается из /pay и кнопки меню)"""
    user_id = msg.sender.user_id if hasattr(msg, 'sender') else msg.user.user_id
    logging.info(f"cmd_pay: user_id={user_id}")

    try:
        await save_paywall_conversion(user_id=user_id, paywall_source="command_pay")
        import asyncio
        asyncio.create_task(send_conversion_event(user_id, 'paywall'))
    except Exception as e:
        logging.error(f"Error saving paywall conversion: {e}", exc_info=True)

    if hasattr(msg, 'reply'):
        await msg.reply(_PAY_TEXT, keyboard=make_payment_kb(), format='html')
    else:
        await msg.send(_PAY_TEXT, keyboard=make_payment_kb(), format='html')


@router.on_command('pay')
async def cmd_pay(ctx: aiomax.CommandContext, cursor: fsm.FSMCursor):
    """Команда /pay — показывает меню оплаты"""
    cursor.clear()
    await cmd_pay_internal(ctx)


@router.on_button_callback(lambda data: data.payload == 'remind_pay')
async def handle_remind_pay(cb: aiomax.Callback, cursor: fsm.FSMCursor):
    """Кнопка «Оплатить» из напоминания (send_message.py --payment-reminder)"""
    cursor.clear()
    user_id = cb.user.user_id
    logging.info(f"remind_pay callback from user {user_id}")

    try:
        await save_paywall_conversion(user_id=user_id, paywall_source="remind_pay")
        import asyncio
        asyncio.create_task(send_conversion_event(user_id, 'paywall'))
    except Exception as e:
        logging.error(f"Error saving paywall conversion: {e}", exc_info=True)

    await cb.send(_PAY_TEXT, keyboard=make_payment_kb(), format='html')


@router.on_button_callback(lambda data: data.payload.startswith('pay_'))
async def handle_payment_selection(cb: aiomax.Callback, cursor: fsm.FSMCursor):
    """Обработка выбора пакета оплаты"""
    payload = cb.payload
    package = PACKAGES.get(payload)
    
    if not package:
        await cb.answer("Неизвестный пакет оплаты")
        return
    
    user_id = cb.user.user_id
    logging.info(f"Payment package selected: {package['id']} by user {user_id}")
    
    cursor.change_data({'package': package})
    
    # Проверяем, есть ли сохраненный email
    saved_email = await get_user_email(user_id)
    
    if saved_email:
        cursor.change_data({'package': package, 'email': saved_email})
        cursor.change_state(STATE_CONFIRMING_EMAIL)
        await bot.send_message(
            f"📧 Для чека используем этот email?\n\n<b>{saved_email}</b>",
            user_id=user_id,
            keyboard=make_email_confirmation_kb(),
            format='html'
        )
    else:
        cursor.change_state(STATE_WAITING_EMAIL)
        await bot.send_message(
            "📧 <b>Нужен email для чека</b>\n\n"
            "Напишите ваш email <b>сюда в чат</b> (в поле сообщения внизу) и нажмите отправить — на него придёт чек после оплаты.",
            user_id=user_id,
            keyboard=make_back_to_menu_kb(),
            format='html'
        )


@router.on_message(filters.state(STATE_WAITING_EMAIL))
async def handle_email_input(message: aiomax.Message, cursor: fsm.FSMCursor):
    """Обработка ввода email"""
    text = (message.content or "").strip()
    
    if text.startswith("/"):
        if text == "/cancel":
            cursor.clear()
            await message.reply("❌ Оплата отменена.", keyboard=make_back_to_menu_kb())
        return
    
    email = text.lower().strip()
    
    # Валидация email
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        await message.reply(
            "❌ Некорректный email. Пожалуйста, введите правильный email.\n\n"
            "Пример: user@example.com"
        )
        return
    
    data = cursor.get_data() or {}
    data['email'] = email
    cursor.change_data(data)
    cursor.change_state(STATE_CONFIRMING_EMAIL)
    
    await message.reply(
        f"📧 Ваш email: <b>{email}</b>\n\nВсё верно?",
        keyboard=make_email_confirmation_kb(),
        format='html'
    )


@router.on_button_callback(lambda data: data.payload == 'email_confirm')
async def handle_email_confirm(cb: aiomax.Callback, cursor: fsm.FSMCursor):
    """Подтверждение email — создаём платёж в ЮKassa"""
    if not config.yookassa_shop_id or not config.yookassa_secret_key:
        await bot.send_message(
            "Оплата временно недоступна (не настроены ключи ЮKassa).",
            user_id=cb.user.user_id,
            keyboard=make_back_to_menu_kb()
        )
        cursor.clear()
        return

    data = cursor.get_data() or {}
    email = data.get('email')
    package = data.get('package')
    user_id = cb.user.user_id

    if not email or not package:
        await bot.send_message(
            "Ошибка. Нажмите ◀ В меню и попробуйте снова.",
            user_id=cb.user.user_id,
            keyboard=make_back_to_menu_kb()
        )
        cursor.clear()
        return

    # Сохраняем email
    await update_user_email(user_id, email)
    
    await bot.send_message("⏳ Создаю ссылку на оплату...", user_id=user_id)
    
    try:
        payment_info = await create_yookassa_payment(
            amount=package['amount_rub'],
            description=f"Оплата: {package['name']}",
            email=email,
            user_id=user_id,
            package_id=package['id']
        )
        
        payment_id = payment_info['id']
        payment_url = payment_info['confirmation']['confirmation_url']
        
        # Сохраняем в БД
        await create_payment(
            payment_id=payment_id,
            user_id=user_id,
            package_id=package['id'],
            amount=package['amount'],
            amount_rub=package['amount_rub'],
            email=email
        )
        
        data['payment_id'] = payment_id
        cursor.change_data(data)
        cursor.change_state(STATE_WAITING_PAYMENT)
        
        kb = buttons.KeyboardBuilder()
        kb.row(buttons.LinkButton("💳 Перейти к оплате", payment_url))
        kb.row(buttons.CallbackButton("✅ Я оплатила", "check_payment"))
        kb.row(buttons.CallbackButton("❌ Отмена", "cancel_payment"))
        
        await bot.send_message(
            f"💳 <b>Оплата: {package['name']}</b>\n\n"
            f"Сумма: <b>{package['amount_rub']:.0f}₽</b>\n"
            f"Email для чека: {email}\n\n"
            "👇 Нажмите <b>«Перейти к оплате»</b> — откроется страница оплаты.\n\n"
            "Если вы уже оплатили — нажмите <b>«Я оплатила»</b>: бот проверит платёж и активирует пакет (иногда уведомление от банка приходит с задержкой).",
            user_id=user_id,
            keyboard=kb,
            format='html'
        )
        
    except Exception as e:
        logging.error(f"Error creating payment: {e}", exc_info=True)
        await bot.send_message(
            "❌ Ошибка при создании платежа. Попробуйте позже.",
            user_id=user_id,
            keyboard=make_back_to_menu_kb()
        )
        cursor.clear()


@router.on_button_callback(lambda data: data.payload == 'email_edit')
async def handle_email_edit(cb: aiomax.Callback, cursor: fsm.FSMCursor):
    """Исправление email"""
    cursor.change_state(STATE_WAITING_EMAIL)
    await bot.send_message(
        "📧 Напишите новый email сюда в чат и нажмите отправить:",
        user_id=cb.user.user_id,
        keyboard=make_back_to_menu_kb()
    )


@router.on_button_callback(lambda data: data.payload == 'check_payment')
async def handle_check_payment(cb: aiomax.Callback, cursor: fsm.FSMCursor):
    """
    Ручная проверка статуса платежа.
    Запрашиваем у API ЮKassa реальный статус по payment_id.
    Если FSM потерял payment_id (рестарт бота) — ищем последний pending-платёж в БД.
    """
    data = cursor.get_data() or {}
    payment_id = data.get('payment_id')
    user_id = cb.user.user_id

    # Fallback: если FSM пустой после рестарта — берём из БД
    if not payment_id:
        logging.info(f"No payment_id in FSM for user {user_id}, checking DB")
        pending = await get_latest_pending_payment(user_id)
        if pending:
            payment_id = pending['payment_id']
            logging.info(f"Found pending payment {payment_id} in DB for user {user_id}")
        else:
            await bot.send_message(
                "Платёж не найден. Нажмите ◀ В меню и попробуйте снова.",
                user_id=user_id,
                keyboard=make_back_to_menu_kb()
            )
            cursor.clear()
            return

    try:
        payment_info = await check_payment_status(payment_id)
        status = payment_info.get('status')

        if status == 'succeeded':
            await db_process_successful_payment(payment_id)

            package = data.get('package', {})

            try:
                await save_conversion(
                    user_id=user_id,
                    conversion_type='purchase',
                    conversion_value=package.get('amount_rub', 0),
                    package_id=package.get('id', ''),
                    metadata={'payment_id': payment_id, 'package_name': package.get('name', '')}
                )
                import asyncio
                asyncio.create_task(send_conversion_event(user_id, 'purchase'))
            except Exception as e:
                logging.error(f"Error saving purchase conversion: {e}", exc_info=True)

            package_name = package.get('name', '')
            if not package_name:
                from handlers.pay import PACKAGES_BY_ID as _pkgs
                pkg_id = payment_info.get('metadata', {}).get('package_id', '')
                pkg = _pkgs.get(pkg_id)
                package_name = pkg['name'] if pkg else ''

            await bot.send_message(
                f"✅ <b>Оплата прошла успешно!</b>\n\n"
                f"Пакет «{package_name}» активирован.\n\n"
                "Можешь продолжать гадать! Напиши свой вопрос в чат.",
                user_id=user_id,
                keyboard=make_back_to_menu_kb(),
                format='html'
            )
            cursor.clear()

        elif status == 'pending' or status == 'waiting_for_capture':
            await bot.send_message(
                "⏳ Платёж ещё обрабатывается. Подождите немного и нажмите «Я оплатила» снова.",
                user_id=user_id,
                keyboard=make_back_to_menu_kb()
            )

        elif status == 'canceled':
            await bot.send_message(
                "❌ Платёж отменён.",
                user_id=user_id,
                keyboard=make_back_to_menu_kb()
            )
            cursor.clear()

        else:
            await bot.send_message(
                f"Статус платежа: {status}. Подождите и нажмите «Я оплатила» снова.",
                user_id=user_id,
                keyboard=make_back_to_menu_kb()
            )

    except Exception as e:
        logging.error(f"Error checking payment: {e}", exc_info=True)
        await bot.send_message(
            "❌ Ошибка при проверке платежа. Попробуйте позже.",
            user_id=user_id,
            keyboard=make_back_to_menu_kb()
        )


@router.on_button_callback(lambda data: data.payload == 'cancel_payment')
async def handle_cancel_payment(cb: aiomax.Callback, cursor: fsm.FSMCursor):
    """Отмена платежа"""
    cursor.clear()
    await bot.send_message(
        "❌ Оплата отменена.",
        user_id=cb.user.user_id,
        keyboard=make_back_to_menu_kb()
    )


# ==================== ЮKassa API ====================

async def create_yookassa_payment(
    amount: float,
    description: str,
    email: str,
    user_id: int,
    package_id: str
) -> dict:
    """Создать платёж в ЮKassa"""
    shop_id = config.yookassa_shop_id.get_secret_value()
    secret_key = config.yookassa_secret_key.get_secret_value()
    
    auth = base64.b64encode(f"{shop_id}:{secret_key}".encode()).decode()
    
    idempotence_key = str(uuid.uuid4())
    
    payment_data = {
        "amount": {
            "value": f"{amount:.2f}",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": config.service_url or "https://max-bot-awtw.onrender.com"
        },
        "capture": True,
        "description": description,
        "receipt": {
            "customer": {"email": email},
            "items": [
                {
                    "description": description,
                    "quantity": "1",
                    "amount": {
                        "value": f"{amount:.2f}",
                        "currency": "RUB"
                    },
                    "vat_code": 1,
                    "payment_subject": "service",
                    "payment_mode": "full_payment"
                }
            ]
        },
        "metadata": {
            "user_id": str(user_id),
            "package_id": package_id,
            "email": email
        }
    }
    
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "Idempotence-Key": idempotence_key
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.yookassa.ru/v3/payments",
            headers=headers,
            json=payment_data
        ) as response:
            if response.status in (200, 201):
                return await response.json()
            else:
                error_text = await response.text()
                logging.error(f"YooKassa error: {response.status} - {error_text}")
                raise Exception(f"YooKassa error: {response.status}")


async def check_payment_status(payment_id: str) -> dict:
    """Проверить статус платежа в ЮKassa"""
    shop_id = config.yookassa_shop_id.get_secret_value()
    secret_key = config.yookassa_secret_key.get_secret_value()
    
    auth = base64.b64encode(f"{shop_id}:{secret_key}".encode()).decode()
    
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.yookassa.ru/v3/payments/{payment_id}",
            headers=headers
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                error_text = await response.text()
                logging.error(f"YooKassa check error: {response.status} - {error_text}")
                raise Exception(f"YooKassa error: {response.status}")
