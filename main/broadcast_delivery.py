"""Общая логика финализации broadcast-отправок."""
from typing import Awaitable, Callable


async def finalize_broadcast_send(
    success: bool,
    unreachable: bool,
    mark_sent: Callable[[], Awaitable[bool]],
) -> str:
    """
    Завершить попытку отправки nudge/reminder.

    Returns: 'sent' | 'blocked' | 'failed'
    """
    if success:
        await mark_sent()
        return 'sent'
    if unreachable:
        await mark_sent()
        return 'blocked'
    return 'failed'
