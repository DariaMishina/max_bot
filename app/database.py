"""PostgreSQL app_bot_db — гости, баланс, расклады."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg

from app.config import app_config

FREE_DIVINATIONS_START = 3


class AppDatabase:
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                host=app_config.app_db_host,
                port=app_config.app_db_port,
                database=app_config.app_db_name,
                user=app_config.app_db_user.get_secret_value(),
                password=app_config.app_db_password.get_secret_value(),
                min_size=1,
                max_size=5,
                command_timeout=60,
            )
            logging.info(
                "App DB pool: host=%s db=%s",
                app_config.app_db_host,
                app_config.app_db_name,
            )
        return cls._pool

    @classmethod
    async def close_pool(cls) -> None:
        if cls._pool:
            await cls._pool.close()
            cls._pool = None

    @classmethod
    async def fetch_one(cls, query: str, *args) -> Optional[asyncpg.Record]:
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    @classmethod
    async def fetch_all(cls, query: str, *args) -> List[asyncpg.Record]:
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)

    @classmethod
    async def execute(cls, query: str, *args) -> str:
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)


async def create_guest(install_id: Optional[str] = None) -> uuid.UUID:
    """Новый гость + баланс с 3 бесплатными раскладами."""
    pool = await AppDatabase.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO app_users (is_guest, install_id)
                VALUES (TRUE, $1)
                RETURNING user_id
                """,
                install_id,
            )
            user_id = row["user_id"]
            await conn.execute(
                """
                INSERT INTO app_user_balances (
                    user_id, free_divinations_remaining, paid_divinations_remaining
                )
                VALUES ($1, $2, 0)
                """,
                user_id,
                FREE_DIVINATIONS_START,
            )
            logging.info("App guest created: %s", user_id)
            return user_id


async def touch_user(user_id: uuid.UUID) -> None:
    await AppDatabase.execute(
        "UPDATE app_users SET last_active_at = NOW() WHERE user_id = $1",
        user_id,
    )


async def get_user_balance(user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    row = await AppDatabase.fetch_one(
        """
        SELECT free_divinations_remaining,
               paid_divinations_remaining,
               unlimited_until,
               total_divinations_used,
               updated_at
        FROM app_user_balances
        WHERE user_id = $1
        """,
        user_id,
    )
    if not row:
        return None
    return dict(row)


async def can_user_divinate(user_id: uuid.UUID) -> tuple[bool, str]:
    balance = await get_user_balance(user_id)
    if not balance:
        return False, "no_balance"

    unlimited_until = balance["unlimited_until"]
    if unlimited_until and unlimited_until > datetime.now():
        return True, "unlimited"

    if balance["free_divinations_remaining"] > 0:
        return True, "free"

    if balance["paid_divinations_remaining"] > 0:
        return True, "paid"

    return False, "no_balance"


async def use_divination(user_id: uuid.UUID) -> bool:
    pool = await AppDatabase.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            balance = await conn.fetchrow(
                """
                SELECT free_divinations_remaining,
                       paid_divinations_remaining,
                       unlimited_until
                FROM app_user_balances
                WHERE user_id = $1
                FOR UPDATE
                """,
                user_id,
            )
            if not balance:
                return False

            now = datetime.now()
            if balance["unlimited_until"] and balance["unlimited_until"] > now:
                await conn.execute(
                    """
                    UPDATE app_user_balances
                    SET total_divinations_used = total_divinations_used + 1,
                        updated_at = NOW()
                    WHERE user_id = $1
                    """,
                    user_id,
                )
                return True

            if balance["free_divinations_remaining"] > 0:
                await conn.execute(
                    """
                    UPDATE app_user_balances
                    SET free_divinations_remaining = free_divinations_remaining - 1,
                        total_divinations_used = total_divinations_used + 1,
                        updated_at = NOW()
                    WHERE user_id = $1
                    """,
                    user_id,
                )
                return True

            if balance["paid_divinations_remaining"] > 0:
                await conn.execute(
                    """
                    UPDATE app_user_balances
                    SET paid_divinations_remaining = paid_divinations_remaining - 1,
                        total_divinations_used = total_divinations_used + 1,
                        updated_at = NOW()
                    WHERE user_id = $1
                    """,
                    user_id,
                )
                return True

            return False


async def save_divination(
    user_id: uuid.UUID,
    *,
    divination_type: str,
    question: str,
    selected_cards: Optional[List[str]] = None,
    interpretation: Optional[str] = None,
    is_free: bool = True,
) -> Optional[int]:
    cards_json = json.dumps(selected_cards) if selected_cards else None
    row = await AppDatabase.fetch_one(
        """
        INSERT INTO app_divinations (
            user_id, divination_type, question, selected_cards, interpretation, is_free
        )
        VALUES ($1, $2, $3, $4::jsonb, $5, $6)
        RETURNING id
        """,
        user_id,
        divination_type,
        question,
        cards_json,
        interpretation,
        is_free,
    )
    return int(row["id"]) if row else None


async def get_divination(divination_id: int, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    row = await AppDatabase.fetch_one(
        """
        SELECT id, divination_type, question, selected_cards, interpretation, is_free, created_at
        FROM app_divinations
        WHERE id = $1 AND user_id = $2
        """,
        divination_id,
        user_id,
    )
    if not row:
        return None
    data = dict(row)
    if isinstance(data.get("selected_cards"), str):
        data["selected_cards"] = json.loads(data["selected_cards"])
    return data


async def get_user(user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    row = await AppDatabase.fetch_one(
        """
        SELECT user_id, is_guest, install_id, created_at, last_active_at
        FROM app_users
        WHERE user_id = $1
        """,
        user_id,
    )
    return dict(row) if row else None


async def list_divinations(user_id: uuid.UUID, limit: int = 20) -> List[Dict[str, Any]]:
    rows = await AppDatabase.fetch_all(
        """
        SELECT id, divination_type, question, selected_cards, interpretation, is_free, created_at
        FROM app_divinations
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )
    result = []
    for row in rows:
        item = dict(row)
        cards = item.get("selected_cards")
        if isinstance(cards, str):
            item["selected_cards"] = json.loads(cards)
        result.append(item)
    return result
