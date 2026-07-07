"""Ошибки доставки сообщений в Max."""
import logging

from main.database import update_user_blocked_status


def is_unreachable_user_error(exc: Exception) -> bool:
    """Пользователь недоступен: удалил бота, чат не найден, диалог приостановлен."""
    msg = str(exc).lower()
    exc_name = type(exc).__name__.lower()
    return (
        "blocked" in msg
        or "forbidden" in msg
        or "chat.denied" in msg
        or "dialog.suspended" in msg
        or "chat not found" in msg
        or "user not found" in msg
        or ("not found" in msg and "chat" in msg)
        or exc_name == "chatnotfound"
    )


async def mark_user_unreachable(user_id: int, error: Exception) -> None:
    """Пометить пользователя недоступным, чтобы рассылки его больше не выбирали."""
    try:
        await update_user_blocked_status(user_id, True)
        logging.info(f"User {user_id} unreachable ({error}), is_blocked=True")
    except Exception as e:
        logging.error(f"Failed to mark user {user_id} blocked: {e}", exc_info=True)
