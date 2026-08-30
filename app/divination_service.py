"""Ядро толкования для Android API — без Max."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import List, Optional

from handlers.tarot_cards import TAROT_CARDS, get_random_cards
from main.llm_divination import interpret_tarot_with_llm

from app.database import (
    can_user_divinate,
    get_user_balance,
    save_divination,
    touch_user,
    use_divination,
)


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


def _validate_card_ids(card_ids: List[str]) -> None:
    if len(card_ids) != 3:
        raise DivinationError("invalid_cards", "Нужно ровно 3 карты")
    for card_id in card_ids:
        if card_id not in TAROT_CARDS:
            raise DivinationError("invalid_cards", f"Неизвестная карта: {card_id}")


async def run_tarot(
    user_id: uuid.UUID,
    question: str,
    *,
    card_ids: Optional[List[str]] = None,
    random_cards: bool = False,
) -> TarotResult:
    question = (question or "").strip()
    if not question:
        raise DivinationError("empty_question", "Вопрос не может быть пустым")

    can, _access = await can_user_divinate(user_id)
    if not can:
        raise DivinationError("no_balance", "Закончились расклады")

    balance_before = await get_user_balance(user_id)
    is_free = bool(balance_before and balance_before["free_divinations_remaining"] > 0)

    if random_cards:
        card_ids = get_random_cards(3)
    if not card_ids:
        raise DivinationError("invalid_cards", "Не указаны карты")
    _validate_card_ids(card_ids)

    interpretation = await interpret_tarot_with_llm(question, card_ids)

    if not await use_divination(user_id):
        raise DivinationError("deduct_failed", "Не удалось списать расклад")

    divination_id = await save_divination(
        user_id,
        divination_type="Таро",
        question=question,
        selected_cards=card_ids,
        interpretation=interpretation,
        is_free=is_free,
    )
    if not divination_id:
        raise DivinationError("save_failed", "Не удалось сохранить расклад")

    await touch_user(user_id)
    balance_after = await get_user_balance(user_id)

    return TarotResult(
        divination_id=divination_id,
        question=question,
        card_ids=card_ids,
        interpretation=interpretation,
        is_free=is_free,
        balance_after=balance_after or {},
    )
