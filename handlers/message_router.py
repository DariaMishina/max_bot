"""Deterministic routing for all non-command text messages.

aiomax 2.12 schedules every matching handler as an independent task.  Keeping
exact-text, state and catch-all handlers registered separately therefore lets
one message enter several flows.  This module is deliberately the only
``on_message`` subscriber in the application.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict
import logging
from weakref import WeakValueDictionary

import aiomax
from aiomax import fsm

from handlers import common, divination, feedback, pay


router = aiomax.Router()

_MAX_PROCESSED_MESSAGE_IDS = 4096
_processed_message_ids: OrderedDict[tuple[int, str], None] = OrderedDict()
_user_locks: WeakValueDictionary[int, asyncio.Lock] = WeakValueDictionary()


def _user_lock(user_id: int) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[user_id] = lock
    return lock


def _claim_message(user_id: int, message_id: str | None) -> bool:
    """Return False for an update already handled by this process."""
    if not message_id:
        return True

    key = (user_id, message_id)
    if key in _processed_message_ids:
        _processed_message_ids.move_to_end(key)
        return False

    _processed_message_ids[key] = None
    if len(_processed_message_ids) > _MAX_PROCESSED_MESSAGE_IDS:
        _processed_message_ids.popitem(last=False)
    return True


NAVIGATION_HANDLERS = {
    "Открыть приложение ✧": common.open_webapp_button,
    "Мой баланс 💎": common.balance_menu_button,
    "Мои гадания 🔮": common.show_balance_button,
    "Новый расклад 🃏": common.new_divination_button,
    "Купить расклады 💎": common.buy_button,
    "Карта дня ✨": common.daily_card_button,
    "Личная консультация 🔮": common.consultation_menu_button,
}

STATE_HANDLERS = {
    "waiting_feedback_paid": feedback.handle_feedback_paid_text,
    "waiting_feedback": feedback.handle_feedback,
    pay.STATE_WAITING_EMAIL: pay.handle_email_input,
    divination.STATE_WAITING_FOR_NEW_QUESTION: divination.handle_new_divination_question,
    divination.STATE_CHOOSING_DIVINATION: divination.handle_divination_type_choice,
    divination.STATE_WAITING_FOR_QUESTION: divination.process_divination_question,
    divination.STATE_SELECTING_CARDS: divination.handle_cards_input_from_selection,
    divination.STATE_WAITING_FOR_CARDS_INPUT: divination.handle_cards_input,
    divination.STATE_CHATTING: divination.handle_follow_up,
}


async def route_text_message(message: aiomax.Message, cursor: fsm.FSMCursor) -> None:
    """Route one message once, preserving arrival order for each user."""
    user_id = message.sender.user_id
    async with _user_lock(user_id):
        message_id = getattr(message, "id", None)
        if not _claim_message(user_id, message_id):
            logging.info("Duplicate message ignored: user_id=%s message_id=%s", user_id, message_id)
            return

        text = (message.content or "").strip()
        navigation_handler = NAVIGATION_HANDLERS.get(text)
        if navigation_handler is not None:
            await navigation_handler(message, cursor)
            return

        state = cursor.get_state()
        state_handler = STATE_HANDLERS.get(state)
        if state_handler is not None:
            await state_handler(message, cursor)
            return

        if state is None:
            await divination.handle_free_text_question(message, cursor)
            return

        logging.warning(
            "Message ignored in unknown FSM state: user_id=%s state=%r message_id=%s",
            user_id,
            state,
            message_id,
        )


@router.on_message()
async def handle_text_message(message: aiomax.Message, cursor: fsm.FSMCursor):
    await route_text_message(message, cursor)


def reset_routing_cache() -> None:
    """Clear process-local routing state; intended for isolated tests."""
    _processed_message_ids.clear()
    _user_locks.clear()
