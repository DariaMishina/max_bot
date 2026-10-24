"""Background MAX delivery with reply binding, audit and circuit breaker."""
import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from main.botdef import bot
from main.database import (
    get_reply_context,
    invalidate_reply_message,
    log_outbound_delivery,
    save_bot_reply_message,
)
from main.send_errors import (
    is_invalid_reply_error,
    is_profile_limited_error,
    is_transient_send_error,
    is_unreachable_user_error,
    mark_user_unreachable,
)

PROFILE_LIMIT_BACKOFF_SECONDS = 30 * 60
_profile_limited_until = 0.0


@dataclass(frozen=True)
class ReplyTarget:
    message_id: Optional[str]
    source: str


def profile_circuit_is_open() -> bool:
    return time.monotonic() < _profile_limited_until


def reset_profile_circuit() -> None:
    global _profile_limited_until
    _profile_limited_until = 0.0


def open_profile_circuit() -> None:
    global _profile_limited_until
    _profile_limited_until = max(
        _profile_limited_until, time.monotonic() + PROFILE_LIMIT_BACKOFF_SECONDS
    )
    logging.critical(
        "MAX profile circuit breaker opened for %s seconds",
        PROFILE_LIMIT_BACKOFF_SECONDS,
    )


def _candidate_columns(touch_type: str) -> tuple[tuple[str, str], ...]:
    if touch_type.startswith("payment"):
        return (
            ("last_callback_message_id", "callback_message"),
            ("last_user_message_id", "user_message"),
            ("last_bot_message_id", "bot_message"),
        )
    return (
        ("last_user_message_id", "user_message"),
        ("last_callback_message_id", "callback_message"),
        ("last_bot_message_id", "bot_message"),
    )


async def choose_reply_target(
    user_id: int,
    touch_type: str,
    explicit_reply_message_id: Optional[str] = None,
    explicit_reply_source: str = "explicit",
    exclude_message_id: Optional[str] = None,
) -> ReplyTarget:
    if explicit_reply_message_id and explicit_reply_message_id != exclude_message_id:
        return ReplyTarget(str(explicit_reply_message_id), explicit_reply_source)
    context = await get_reply_context(user_id) or {}
    for column, source in _candidate_columns(touch_type):
        message_id = context.get(column)
        if message_id and message_id != exclude_message_id:
            return ReplyTarget(str(message_id), source)
    return ReplyTarget(None, "no_context")


async def _delivery_log(**values) -> None:
    await log_outbound_delivery(**values)
    logging.info(
        "outbound_touch user_id=%s touch_type=%s stage=%s reply_source=%s "
        "reply_message_id=%s attempt=%s success=%s error=%s circuit_open=%s",
        values.get("user_id"), values.get("touch_type"), values.get("touch_stage"),
        values.get("reply_source"), values.get("reply_message_id"),
        values.get("attempt"), values.get("success"), values.get("error_code"),
        values.get("circuit_open"),
    )


async def send_background_message(
    user_id: int,
    text: str | None,
    *,
    touch_type: str,
    touch_stage: Optional[str] = None,
    format: Optional[str] = "html",
    keyboard=None,
    attachments=None,
    explicit_reply_message_id: Optional[str] = None,
    explicit_reply_source: str = "explicit",
    reply_target_resolved: bool = False,
    allow_plain_fallback: bool = True,
) -> tuple[bool, bool]:
    """Return (delivered, unreachable_user), preserving broadcast contracts."""
    if profile_circuit_is_open():
        await _delivery_log(
            user_id=user_id, touch_type=touch_type, touch_stage=touch_stage,
            reply_source="no_context", success=False, api_result="skipped",
            error_code="profile_circuit_open", circuit_open=True,
        )
        return False, False

    target = (
        ReplyTarget(explicit_reply_message_id, explicit_reply_source)
        if reply_target_resolved
        else await choose_reply_target(
            user_id, touch_type, explicit_reply_message_id, explicit_reply_source
        )
    )
    for attempt in (1, 2):
        if not target.message_id and not allow_plain_fallback:
            await _delivery_log(
                user_id=user_id, touch_type=touch_type, touch_stage=touch_stage,
                reply_source="no_context", success=False, api_result="skipped",
                error_code="no_reply_context", attempt=attempt, circuit_open=False,
            )
            return False, False
        try:
            message = await bot.send_message(
                text,
                user_id=user_id,
                keyboard=keyboard,
                format=format,
                attachments=attachments,
                reply_to=target.message_id,
            )
            message_id = getattr(message, "id", None)
            chat_id = getattr(getattr(message, "recipient", None), "chat_id", None)
            if message_id:
                try:
                    await save_bot_reply_message(
                        user_id, chat_id, message_id,
                        datetime.now(timezone.utc).replace(tzinfo=None),
                    )
                except Exception as context_error:
                    logging.error(
                        "Message delivered but bot reply context was not saved: %s",
                        context_error, exc_info=True,
                    )
            await _delivery_log(
                user_id=user_id, touch_type=touch_type, touch_stage=touch_stage,
                reply_message_id=target.message_id, reply_source=target.source,
                sent_as_reply=bool(target.message_id), success=True,
                api_result="sent", outbound_message_id=message_id, attempt=attempt,
                circuit_open=False,
            )
            return True, False
        except Exception as exc:
            if is_profile_limited_error(exc):
                open_profile_circuit()
                await _delivery_log(
                    user_id=user_id, touch_type=touch_type, touch_stage=touch_stage,
                    reply_message_id=target.message_id, reply_source=target.source,
                    sent_as_reply=bool(target.message_id), success=False,
                    api_result="error", error_code="profile_limited", attempt=attempt,
                    circuit_open=True,
                )
                return False, False
            if target.message_id and is_invalid_reply_error(exc) and attempt == 1:
                invalid_id = target.message_id
                await invalidate_reply_message(user_id, invalid_id)
                await _delivery_log(
                    user_id=user_id, touch_type=touch_type, touch_stage=touch_stage,
                    reply_message_id=invalid_id, reply_source=target.source,
                    sent_as_reply=True, success=False, api_result="retry",
                    error_code="invalid_reply", attempt=attempt, circuit_open=False,
                )
                target = await choose_reply_target(
                    user_id, touch_type, explicit_reply_message_id,
                    explicit_reply_source, exclude_message_id=invalid_id,
                )
                continue
            if is_transient_send_error(exc) and attempt == 1:
                await _delivery_log(
                    user_id=user_id, touch_type=touch_type, touch_stage=touch_stage,
                    reply_message_id=target.message_id, reply_source=target.source,
                    sent_as_reply=bool(target.message_id), success=False,
                    api_result="retry", error_code="transient_api_error",
                    attempt=attempt, circuit_open=False,
                )
                await asyncio.sleep(1)
                continue
            unreachable = is_unreachable_user_error(exc)
            if unreachable:
                await mark_user_unreachable(user_id, exc)
            await _delivery_log(
                user_id=user_id, touch_type=touch_type, touch_stage=touch_stage,
                reply_message_id=target.message_id, reply_source=target.source,
                sent_as_reply=bool(target.message_id), success=False,
                api_result="error", error_code=type(exc).__name__, attempt=attempt,
                circuit_open=profile_circuit_is_open(),
            )
            if not unreachable:
                logging.error("MAX background send failed for user %s: %s", user_id, exc)
            return False, unreachable
    return False, False
