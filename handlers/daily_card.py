"""
Обработчик ежедневной карты дня — адаптировано для Max (aiomax).

Ключевые отличия:
- bot.send_message() вместо bot.send_photo()
- bot.upload_image() для отправки изображений
- CallbackButton вместо InlineKeyboardButton
"""
import logging
import random
import os
import asyncio
from datetime import datetime
from typing import List, Optional

import aiomax
from aiomax import buttons

from keyboards.main_menu import make_back_to_menu_kb
from main.botdef import bot
from main.database import (
    get_all_users,
    update_user_blocked_status,
    is_send_blocked_error,
    get_user_balance,
    can_user_divinate,
    update_user_daily_card_subscription,
    get_user_daily_card_subscription
)
from handlers.tarot_cards import get_all_available_cards, get_card_info, get_card_image_path

router = aiomax.Router()


async def create_daily_card_keyboard(user_id: int) -> buttons.KeyboardBuilder:
    """Создать клавиатуру с 3 кнопками для выбора карты дня"""
    kb = buttons.KeyboardBuilder()
    
    all_cards = get_all_available_cards()
    if len(all_cards) < 3:
        selected_cards = all_cards
    else:
        selected_cards = random.sample(all_cards, 3)
    
    for i, card_id in enumerate(selected_cards, 1):
        kb.row(buttons.CallbackButton(f"✨ Карта {i}", f"daily_card_{card_id}"))
    
    kb.row(buttons.CallbackButton("🔮 Проверить баланс", "daily_card_check_balance"))
    
    can_divinate, access_type = await can_user_divinate(user_id)
    if not can_divinate:
        kb.row(buttons.CallbackButton("💳 Оплатить", "daily_card_pay"))
    
    kb.row(buttons.CallbackButton("❌ Отписаться от карты дня", "daily_card_unsubscribe"))
    kb.row(buttons.CallbackButton("◀ В меню", "back_to_menu"))
    
    return kb


async def send_daily_card_message(user_id: int, auto_update_blocked_status: bool = True) -> bool:
    """Отправить сообщение с картой дня пользователю"""
    try:
        kb = await create_daily_card_keyboard(user_id)
        
        await bot.send_message(
            "🌅 <b>Доброе утро! Выбери свою карту дня</b>\n\n"
            "Каждый день — новый ответ Вселенной. "
            "Нажми на одну из карт, чтобы узнать послание дня ✨",
            user_id=user_id,
            keyboard=kb,
            format='html'
        )
        return True
    except Exception as e:
        error_str = str(e).lower()
        if is_send_blocked_error(e) or 'chat not found' in error_str:
            if auto_update_blocked_status:
                await update_user_blocked_status(user_id, True)
                logging.info(f"User {user_id} blocked the bot, updated status")
            return False
        logging.error(f"Error sending daily card to user {user_id}: {e}", exc_info=True)
        return False


async def send_daily_card_to_all_users(user_ids: Optional[List[int]] = None) -> dict:
    """Отправить карту дня всем пользователям (или списку)"""
    results = {'sent': 0, 'failed': 0, 'blocked': 0, 'skipped': 0}
    
    if user_ids:
        targets = [{'user_id': uid} for uid in user_ids]
    else:
        targets = await get_all_users(include_blocked=False, include_unsubscribed_daily_card=False)
    
    for user in targets:
        uid = user['user_id']
        
        try:
            is_subscribed = await get_user_daily_card_subscription(uid)
            if not is_subscribed:
                results['skipped'] += 1
                continue
            
            success = await send_daily_card_message(uid)
            if success:
                results['sent'] += 1
            else:
                results['blocked'] += 1
            
            await asyncio.sleep(0.1)
            
        except Exception as e:
            logging.error(f"Error processing user {uid}: {e}", exc_info=True)
            results['failed'] += 1
    
    logging.info(f"Daily card results: {results}")
    return results


# ==================== Callback handlers ====================

@router.on_button_callback(lambda data: data.payload.startswith('daily_card_') and not data.payload.startswith('daily_card_check') and not data.payload.startswith('daily_card_pay') and not data.payload.startswith('daily_card_unsub'))
async def handle_daily_card_choice(cb: aiomax.Callback):
    """Обработка выбора карты дня"""
    card_id = cb.payload[len('daily_card_'):]
    card_info = get_card_info(card_id)
    user_id = cb.user.user_id
    chat_id = cb.message.recipient.chat_id
    
    logging.info(f"Daily card chosen: {card_id} ({card_info['name']}) by user {user_id}")
    
    # Отправляем изображение
    image_path = get_card_image_path(card_id)
    if os.path.exists(image_path):
        try:
            attachment = await bot.upload_image(image_path)
            await bot.send_message(None, chat_id=chat_id, attachments=attachment)
        except Exception as e:
            logging.warning(f"Не удалось отправить изображение карты: {e}")
    
    # Текст карты — в чат, а не во всплывающее окно
    card_text = (
        f"🃏 <b>Твоя карта дня: {card_info['name']}</b>\n\n"
        f"✨ <b>Значение:</b> {card_info['meaning']}\n\n"
        "Пусть этот день будет наполнен мудростью этой карты! 🌟\n\n"
        "💬 Хочешь узнать больше? Напиши свой вопрос и выбери тип гадания."
    )
    await bot.send_message(
        card_text,
        chat_id=chat_id,
        keyboard=make_back_to_menu_kb(),
        format='html'
    )
    await cb.answer(notification="🃏")


@router.on_button_callback(lambda data: data.payload == 'daily_card_check_balance')
async def handle_daily_card_balance(cb: aiomax.Callback):
    """Проверка баланса из карты дня"""
    user_id = cb.user.user_id
    chat_id = cb.message.recipient.chat_id
    balance = await get_user_balance(user_id)
    
    if balance:
        text = (
            f"🔮 <b>Ваш баланс</b>\n\n"
            f"🆓 Бесплатных: {balance['free_divinations_remaining']}\n"
            f"💎 Платных: {balance['paid_divinations_remaining']}\n"
            f"📊 Использовано: {balance['total_divinations_used']}"
        )
    else:
        text = "🔮 Баланс не найден. Напишите боту, чтобы зарегистрироваться."
    
    await bot.send_message(text, chat_id=chat_id, keyboard=make_back_to_menu_kb(), format='html')
    await cb.answer(notification="🔮")


@router.on_button_callback(lambda data: data.payload == 'daily_card_pay')
async def handle_daily_card_pay(cb: aiomax.Callback):
    """Переход к оплате из карты дня"""
    from keyboards.pay import make_payment_kb
    
    chat_id = cb.message.recipient.chat_id
    await bot.send_message(
        "💎 Выберите пакет для покупки:",
        chat_id=chat_id,
        keyboard=make_payment_kb()
    )
    await cb.answer(notification="💎")


@router.on_button_callback(lambda data: data.payload == 'daily_card_unsubscribe')
async def handle_daily_card_unsubscribe(cb: aiomax.Callback):
    """Отписка от карты дня"""
    user_id = cb.user.user_id
    chat_id = cb.message.recipient.chat_id
    await update_user_daily_card_subscription(user_id, False)
    
    kb = buttons.KeyboardBuilder()
    kb.row(buttons.CallbackButton("🔄 Подписаться обратно", "daily_card_resubscribe"))
    kb.row(buttons.CallbackButton("◀ В меню", "back_to_menu"))
    
    await bot.send_message(
        "❌ Вы отписались от ежедневной карты дня.\n\n"
        "Чтобы подписаться обратно, нажмите кнопку ниже.",
        chat_id=chat_id,
        keyboard=kb
    )
    await cb.answer(notification="❌")


@router.on_button_callback(lambda data: data.payload == 'daily_card_resubscribe')
async def handle_daily_card_resubscribe(cb: aiomax.Callback):
    """Повторная подписка на карту дня"""
    user_id = cb.user.user_id
    chat_id = cb.message.recipient.chat_id
    await update_user_daily_card_subscription(user_id, True)
    
    await bot.send_message(
        "✅ Вы снова подписаны на ежедневную карту дня! 🌅",
        chat_id=chat_id,
        keyboard=make_back_to_menu_kb()
    )
    await cb.answer(notification="✅")
