"""Минимальный безопасный контекст для персонализированных рассылок."""
from __future__ import annotations

from typing import Any

from main.database import get_user_divinations

MAX_RECENT_DIVINATIONS = 3
MAX_QUESTION_CHARS = 300
MAX_TYPE_CHARS = 80


def _clean_text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


async def load_broadcast_context(user_id: int) -> dict[str, Any]:
    divinations = await get_user_divinations(user_id, limit=MAX_RECENT_DIVINATIONS)
    recent = []
    for divination in divinations:
        question = _clean_text(divination.get("question"), MAX_QUESTION_CHARS)
        divination_type = _clean_text(
            divination.get("divination_type"), MAX_TYPE_CHARS
        )
        if question:
            recent.append(
                {
                    "type": divination_type or "расклад",
                    "question": question,
                }
            )
    return {"recent_divinations": recent}


def has_personalization_facts(context: dict[str, Any]) -> bool:
    return bool(context.get("recent_divinations"))
