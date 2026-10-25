"""Persistent DeepSeek request budget used only by the Android application."""
from __future__ import annotations

import logging

from app.config import app_config
from app.database import AppDatabase


class AppLlmBudgetExceeded(Exception):
    pass


async def reserve_llm_request(operation: str) -> int:
    """Atomically consume one rolling-24h request slot across API workers.

    Reservations deliberately survive provider failures: failed upstream calls may
    still cost money and must count toward the emergency ceiling. They are not tied
    to a user: the budget is global, and a foreign-key check from a second database
    transaction would deadlock with the caller's lock on that user.
    """
    limit = app_config.app_deepseek_daily_request_limit
    pool = await AppDatabase.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('app-llm-budget-v1', 0))")
            used = await conn.fetchval(
                "SELECT COUNT(*) FROM app_llm_requests WHERE created_at >= NOW() - INTERVAL '24 hours'"
            )
            if int(used or 0) >= limit:
                logging.warning("App LLM request denied: reason=daily_budget operation=%s", operation)
                raise AppLlmBudgetExceeded
            request_id = await conn.fetchval(
                "INSERT INTO app_llm_requests (operation) VALUES ($1) RETURNING id",
                operation,
            )
    return int(request_id)


async def finish_llm_request(request_id: int, *, succeeded: bool) -> None:
    await AppDatabase.execute(
        "UPDATE app_llm_requests SET status = $2, completed_at = NOW() WHERE id = $1",
        request_id,
        "succeeded" if succeeded else "failed",
    )
