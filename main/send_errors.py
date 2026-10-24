"""Ошибки доставки сообщений в Max."""
import logging

from main.database import update_user_blocked_status


def is_profile_limited_error(exc: Exception) -> bool:
    """Global bot profile restriction, not a per-user delivery failure."""
    msg = str(exc).lower()
    return "profile is limited" in msg or "profile.limited" in msg


def is_invalid_reply_error(exc: Exception) -> bool:
    """The reply target is missing, deleted or otherwise unusable."""
    msg = str(exc).lower()
    return (
        "message not found" in msg
        or "message.not.found" in msg
        or "invalid link" in msg
        or "invalid reply" in msg
        or ("reply" in msg and "not found" in msg)
    )


def is_transient_send_error(exc: Exception) -> bool:
    """API failures safe to retry once with the same reply target."""
    msg = str(exc).lower()
    return (
        "too many requests" in msg
        or "rate limit" in msg
        or "temporarily unavailable" in msg
        or "service unavailable" in msg
        or "bad gateway" in msg
        or any(f"http {code}" in msg for code in (429, 500, 502, 503, 504))
    )


def is_unreachable_user_error(exc: Exception) -> bool:
    """Пользователь недоступен: удалил бота, чат не найден, диалог приостановлен."""
    msg = str(exc).lower()
    exc_name = type(exc).__name__.lower()
    return not is_profile_limited_error(exc) and (
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
