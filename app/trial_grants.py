"""Server-owned welcome gift ledger shared by every authentication provider."""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from app.config import app_config

logger = logging.getLogger(__name__)
_ANDROID_ID = re.compile(r"[0-9a-f]{1,16}")


def normalize_device_signal(value: object) -> str | None:
    """Validate format, not authenticity: a modified client can still forge it."""
    if not isinstance(value, str) or len(value) > 64:
        return None
    normalized = value.strip().lower()
    if not _ANDROID_ID.fullmatch(normalized):
        return None
    if int(normalized, 16) == 0 or normalized == "9774d56d682e549c":
        return None
    return normalized


async def claim_trial(
    conn: Any, *, identity_key: str, user_id: uuid.UUID,
    device_signal: object, eligible: bool, amount: int,
) -> int:
    """Called within the account transaction; rollback also rolls back the gift.

    Keep every identity even when its device already claimed a gift. Otherwise
    deleting that account and re-registering on another device resets eligibility.
    The shared transaction lock serializes device claims and the global budget
    across API workers, including requests from different auth providers.
    """
    # Local import avoids a module cycle and preserves the existing HMAC format.
    from app.account_auth import signal_hash

    signal = normalize_device_signal(device_signal)
    device_hash = signal_hash("device", signal)
    await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('app-trial-grants-v1', 0))")
    previous_amount = await conn.fetchval(
        "SELECT granted_amount FROM app_trial_claims WHERE device_hash = $1", device_hash,
    ) if device_hash else None
    device_used = previous_amount is not None
    claim_id = await conn.fetchval(
        """INSERT INTO app_trial_claims (identity_key, device_hash, claimed_user_id, granted_amount)
           VALUES ($1, $2, $3, 0)
           ON CONFLICT (identity_key) DO NOTHING RETURNING id""",
        identity_key, None if device_used else device_hash, user_id,
    )
    if not claim_id:
        return 0
    reason = None
    if not eligible:
        reason = "existing_account"
    elif not device_hash:
        reason = "invalid_device"
    elif device_used:
        reason = "device_used" if previous_amount > 0 else "device_unavailable"
    else:
        granted_today = await conn.fetchval(
            """SELECT COUNT(*) FROM app_trial_claims
               WHERE granted_amount > 0 AND created_at >= LOCALTIMESTAMP - INTERVAL '24 hours'"""
        )
        if granted_today >= app_config.app_trial_daily_limit:
            reason = "daily_limit"
    if reason:
        await conn.execute(
            "UPDATE app_trial_claims SET decision = $2 WHERE id = $1", claim_id, reason,
        )
        # No raw IP, device identifier, login or email in operational logs.
        log = logger.warning if reason == "daily_limit" else logger.info
        log("Welcome gift denied: reason=%s", reason)
        return 0
    await conn.execute(
        """UPDATE app_user_balances
           SET free_divinations_remaining = free_divinations_remaining + $2, updated_at = NOW()
           WHERE user_id = $1""", user_id, amount,
    )
    await conn.execute(
        "UPDATE app_trial_claims SET granted_amount = $2, decision = 'granted' WHERE id = $1", claim_id, amount,
    )
    logger.info("Welcome gift granted: amount=%s", amount)
    return amount
