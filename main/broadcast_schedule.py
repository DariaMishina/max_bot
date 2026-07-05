"""
Расписание отправки рассылок: окно 10:00–20:00 MSK.

Для каждого пользователя вычисляется минута отправки:
  - если есть last_active_at — ближе к часу последней активности (в пределах окна);
  - иначе — детерминированный слот по user_id (hash).
"""
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")

BROADCAST_WINDOW_START_HOUR = 10
BROADCAST_WINDOW_END_HOUR = 20
BROADCAST_TICK_MINUTES = 30


def _minutes_from_midnight(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def _to_msk(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=MSK)
    return dt.astimezone(MSK)


def compute_user_send_minute(
    user_id: int,
    anchor_at: Optional[datetime] = None,
    *,
    last_active_at: Optional[datetime] = None,
) -> int:
    """
    Минута отправки от полуночи MSK в диапазоне [10:00, 20:00).

    anchor_at (или last_active_at) вне окна маппится в окно через modulo.
    """
    anchor = anchor_at if anchor_at is not None else last_active_at
    window_start = BROADCAST_WINDOW_START_HOUR * 60
    window_size = (BROADCAST_WINDOW_END_HOUR - BROADCAST_WINDOW_START_HOUR) * 60

    if anchor is not None:
        la = _to_msk(anchor)
        minute = _minutes_from_midnight(la)
        if window_start <= minute < window_start + window_size:
            return minute
        return window_start + (minute % window_size)

    return window_start + (user_id % window_size)


def is_in_broadcast_window(now: Optional[datetime] = None) -> bool:
    """True, если текущее время попадает в окно рассылок 10:00–20:00 MSK."""
    now = _to_msk(now or datetime.now(MSK))
    current = _minutes_from_midnight(now)
    window_start = BROADCAST_WINDOW_START_HOUR * 60
    window_end = BROADCAST_WINDOW_END_HOUR * 60
    return window_start <= current < window_end


def is_user_due_in_tick(
    user_id: int,
    anchor_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
    tick_minutes: int = BROADCAST_TICK_MINUTES,
    *,
    last_active_at: Optional[datetime] = None,
) -> bool:
    """True, если текущий 30-минутный тик — время отправки для пользователя."""
    now = _to_msk(now or datetime.now(MSK))
    current = _minutes_from_midnight(now)
    send_minute = compute_user_send_minute(
        user_id,
        anchor_at=anchor_at,
        last_active_at=last_active_at,
    )
    return send_minute <= current < send_minute + tick_minutes


def is_same_msk_day(ts: Optional[datetime], now: Optional[datetime] = None) -> bool:
    """True, если ts попадает на ту же календарную дату (MSK), что и now."""
    if ts is None:
        return False
    now = _to_msk(now or datetime.now(MSK))
    return _to_msk(ts).date() == now.date()
