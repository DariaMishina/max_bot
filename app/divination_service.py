"""Tarot and follow-ups for the Android guest; no Max calls or bot tables."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from handlers.tarot_cards import TAROT_CARDS, get_random_cards
from main.llm_divination import interpret_tarot_with_llm, call_deepseek
from app.database import AppDatabase


class DivinationError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass
class TarotResult:
    divination_id: int
    question: str
    card_ids: List[str]
    interpretation: str
    is_free: bool
    balance_after: dict


def validate_question(question: str) -> str:
    question = question.strip()
    if not question:
        raise DivinationError("empty_question", "Вопрос не может быть пустым")
    if len(question) > 1000:
        raise DivinationError("long_question", "Вопрос должен быть не длиннее 1000 символов")
    return question


def _validate_card_ids(card_ids: List[str]) -> None:
    if len(card_ids) != 3 or len(set(card_ids)) != 3:
        raise DivinationError("invalid_cards", "Нужно ровно 3 разные карты")
    if any(card_id not in TAROT_CARDS for card_id in card_ids):
        raise DivinationError("invalid_cards", "Неизвестная карта")


def _decode(value):
    return json.loads(value) if isinstance(value, str) else value


async def run_tarot(
    user_id: uuid.UUID, question: str, *, card_ids: Optional[List[str]] = None,
    random_cards: bool = False, request_id: Optional[uuid.UUID] = None,
) -> TarotResult:
    question = validate_question(question)
    if not random_cards:
        _validate_card_ids(card_ids or [])
    pool = await AppDatabase.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Serialize operations for this guest, including deletion. The balance,
            # saved result and idempotency key commit together only after LLM success.
            if not await conn.fetchval("SELECT user_id FROM app_users WHERE user_id = $1 FOR UPDATE", user_id):
                raise DivinationError("not_found", "Пользователь не найден")
            balance = await conn.fetchrow("SELECT * FROM app_user_balances WHERE user_id = $1 FOR UPDATE", user_id)
            if request_id:
                previous = await conn.fetchrow(
                    "SELECT * FROM app_divinations WHERE user_id = $1 AND request_id = $2", user_id, request_id,
                )
                if previous:
                    return TarotResult(previous["id"], previous["question"], _decode(previous["selected_cards"]),
                                       previous["interpretation"], previous["is_free"], dict(balance))
            unlimited = bool(balance and balance["unlimited_until"] and balance["unlimited_until"] > datetime.now())
            if not balance or not (unlimited or balance["free_divinations_remaining"] > 0 or balance["paid_divinations_remaining"] > 0):
                raise DivinationError("no_balance", "Закончились расклады")
            is_free = not unlimited and balance["free_divinations_remaining"] > 0
            if random_cards:
                card_ids = get_random_cards(3)
            interpretation = await interpret_tarot_with_llm(question, card_ids)
            if not interpretation.strip():
                raise DivinationError("empty_result", "Не удалось получить толкование. Попробуйте снова")
            divination_id = await conn.fetchval(
                """INSERT INTO app_divinations
                (user_id, divination_type, question, selected_cards, interpretation, is_free, request_id)
                VALUES ($1, 'Таро', $2, $3::jsonb, $4, $5, $6) RETURNING id""",
                user_id, question, json.dumps(card_ids), interpretation, is_free, request_id,
            )
            balance_after = await conn.fetchrow(
                """UPDATE app_user_balances SET
                free_divinations_remaining = free_divinations_remaining - $2,
                paid_divinations_remaining = paid_divinations_remaining - $3,
                total_divinations_used = total_divinations_used + 1, updated_at = NOW()
                WHERE user_id = $1 RETURNING *""", user_id, int(is_free), int(not unlimited and not is_free),
            )
            await conn.execute("UPDATE app_users SET last_active_at = NOW() WHERE user_id = $1", user_id)
            return TarotResult(divination_id, question, card_ids, interpretation, is_free, dict(balance_after))


async def run_follow_up(user_id: uuid.UUID, divination_id: int, question: str, request_id: uuid.UUID) -> dict:
    question = validate_question(question)
    pool = await AppDatabase.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.fetchval("SELECT user_id FROM app_users WHERE user_id = $1 FOR UPDATE", user_id)
            row = await conn.fetchrow(
                "SELECT * FROM app_divinations WHERE id = $1 AND user_id = $2 FOR UPDATE", divination_id, user_id,
            )
            if not row:
                raise DivinationError("not_found", "Расклад не найден")
            history = _decode(row["follow_ups"])
            limit = 2 if row["is_free"] else 5
            if not any(item.get("request_id") == str(request_id) for item in history):
                if len(history) >= limit:
                    raise DivinationError("follow_up_limit", "Все уточнения к этому раскладу использованы")
                messages = [
                    {"role": "user", "content": f"Вопрос: {row['question']}\nКарты: {_decode(row['selected_cards'])}"},
                    {"role": "assistant", "content": row["interpretation"]},
                ]
                for item in history:
                    messages.extend([{"role": "user", "content": item["question"]}, {"role": "assistant", "content": item["answer"]}])
                messages.append({"role": "user", "content": question})
                answer = await call_deepseek(
                    messages,
                    "Ты опытный таролог. Ответь по-русски на уточнение к уже проведённому раскладу, "
                    "учитывая его контекст. 2–4 предложения, без markdown и HTML.",
                    max_tokens=500, format_output=False,
                )
                if not answer.strip():
                    raise DivinationError("empty_result", "Не удалось получить ответ. Попробуйте снова")
                history.append({"request_id": str(request_id), "question": question, "answer": answer})
                await conn.execute("UPDATE app_divinations SET follow_ups = $2::jsonb WHERE id = $1", divination_id, json.dumps(history))
            return {"follow_ups": history, "follow_ups_remaining": max(0, limit - len(history))}
