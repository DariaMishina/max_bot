"""Capture MAX message ids before aiomax schedules business handlers."""
import logging
from datetime import datetime, timezone

from main.database import (
    invalidate_reply_message,
    save_bot_start_reply_chat,
    save_callback_reply_message,
    save_user_reply_message,
)


def _event_time(value) -> datetime:
    try:
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OSError):
        return datetime.now(timezone.utc).replace(tzinfo=None)


async def capture_reply_update(update: dict) -> None:
    """Persist reply context without allowing diagnostics to break polling."""
    update_type = update.get("update_type")
    try:
        if update_type == "message_created":
            message = update.get("message") or {}
            sender = message.get("sender") or {}
            recipient = message.get("recipient") or {}
            body = message.get("body") or {}
            user_id = sender.get("user_id")
            chat_id = recipient.get("chat_id")
            message_id = body.get("mid")
            if user_id and chat_id and message_id:
                await save_user_reply_message(
                    int(user_id), int(chat_id), str(message_id),
                    _event_time(message.get("timestamp") or update.get("timestamp")),
                )
        elif update_type == "message_callback":
            callback = update.get("callback") or {}
            message = update.get("message") or {}
            user = callback.get("user") or update.get("user") or {}
            recipient = message.get("recipient") or {}
            body = message.get("body") or {}
            user_id = user.get("user_id")
            chat_id = recipient.get("chat_id")
            message_id = body.get("mid")
            if user_id and chat_id and message_id:
                await save_callback_reply_message(
                    int(user_id), int(chat_id), str(message_id),
                    _event_time(callback.get("timestamp") or update.get("timestamp")),
                )
        elif update_type == "bot_started":
            user = update.get("user") or {}
            if user.get("user_id") and update.get("chat_id"):
                await save_bot_start_reply_chat(int(user["user_id"]), int(update["chat_id"]))
        elif update_type == "message_removed":
            if update.get("user_id") and update.get("message_id"):
                await invalidate_reply_message(
                    int(update["user_id"]), str(update["message_id"])
                )
    except Exception as exc:
        logging.error("Could not capture MAX reply update: %s", exc, exc_info=True)
