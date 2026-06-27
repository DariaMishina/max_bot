"""
Парсинг названий карт Таро из текста пользователя.

Два уровня:
1. Словарь алиасов (быстро, без API)
2. LLM fallback через DeepSeek (опечатки, свободная форма)
"""
from __future__ import annotations

import json
import logging
import re
from typing import Callable, Awaitable

from handlers.tarot_cards import TAROT_CARDS, get_card_info

REQUIRED_CARD_COUNT = 3

RANK_WORDS: dict[int, list[str]] = {
    1: ["туз", "ace", "1"],
    2: ["двойка", "2"],
    3: ["тройка", "3"],
    4: ["четверка", "4", "четв"],
    5: ["пятерка", "5", "пят"],
    6: ["шестерка", "6", "шест"],
    7: ["семерка", "7", "сем"],
    8: ["восьмерка", "8", "восьм"],
    9: ["девятка", "9", "девят"],
    10: ["десятка", "10", "десят"],
    11: ["паж", "page", "валет"],
    12: ["рыцарь", "knight"],
    13: ["королева", "queen"],
    14: ["король", "king"],
}

SUIT_WORDS: dict[str, str] = {
    "кубков": "Cups",
    "кубки": "Cups",
    "кубок": "Cups",
    "cups": "Cups",
    "мечей": "Swords",
    "мечи": "Swords",
    "меч": "Swords",
    "swords": "Swords",
    "жезлов": "Wands",
    "жезлы": "Wands",
    "жезл": "Wands",
    "посохов": "Wands",
    "посохи": "Wands",
    "wands": "Wands",
    "пентаклей": "Pentacles",
    "пентакли": "Pentacles",
    "пентакль": "Pentacles",
    "монет": "Pentacles",
    "монеты": "Pentacles",
    "дисков": "Pentacles",
    "диски": "Pentacles",
    "pentacles": "Pentacles",
}

CARD_PARSE_SYSTEM_PROMPT = (
    "Ты помощник таролога. Определи ровно 3 карты Таро Rider-Waite из текста пользователя "
    "в порядке слева направо (Прошлое, Настоящее, Будущее). "
    "Верни ТОЛЬКО JSON-массив из 3 строк — ID карт из списка ниже. "
    "Если карту нельзя однозначно определить, используй null на этой позиции. "
    "Без markdown и пояснений."
)

CARD_PARSE_USER_TEMPLATE = (
    "Текст пользователя: {text}\n\n"
    "Доступные карты (id — название):\n{catalog}\n\n"
    'Пример ответа: ["16-TheTower", "Cups01", "Swords10"]'
)


def normalize_card_text(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("ё", "е")
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _build_alias_map() -> dict[str, str]:
    aliases: dict[str, str] = {}

    for card_id, info in TAROT_CARDS.items():
        name = info["name"]
        aliases[normalize_card_text(name)] = card_id

        norm = normalize_card_text(name)
        if " " in norm:
            words = norm.split()
            if len(words) >= 2:
                aliases[" ".join(words[1:])] = card_id

        match = re.match(r"^(\d+)-(.+)$", card_id)
        if match:
            num, slug = match.groups()
            slug_words = re.sub(r"([a-z])([A-Z])", r"\1 \2", slug).lower()
            aliases[normalize_card_text(slug_words)] = card_id
            aliases[num.lstrip("0") or "0"] = card_id

        match = re.match(r"^(Cups|Swords|Wands|Pentacles)(\d+)$", card_id)
        if match:
            suit, num = match.groups()
            rank = int(num)
            for rank_word in RANK_WORDS.get(rank, []):
                for suit_word, suit_key in SUIT_WORDS.items():
                    if suit_key == suit:
                        aliases[normalize_card_text(f"{rank_word} {suit_word}")] = card_id

    extra_major = {
        "шут": "00-TheFool",
        "дурак": "00-TheFool",
        "fool": "00-TheFool",
        "жрица": "02-TheHighPriestess",
        "верховная жрица": "02-TheHighPriestess",
        "папа": "05-TheHierophant",
        "иерофант": "05-TheHierophant",
        "влюбленные": "06-TheLovers",
        "колесница": "07-TheChariot",
        "колесо фортуны": "10-WheelOfFortune",
        "колесо": "10-WheelOfFortune",
        "повешенный": "12-TheHangedMan",
        "смерть": "13-Death",
        "умеренность": "14-Temperance",
        "дьявол": "15-TheDevil",
        "башня": "16-TheTower",
        "tower": "16-TheTower",
        "звезда": "17-TheStar",
        "луна": "18-TheMoon",
        "солнце": "19-TheSun",
        "суд": "20-Judgement",
        "мир": "21-TheWorld",
    }
    for alias, card_id in extra_major.items():
        aliases[normalize_card_text(alias)] = card_id

    return aliases


ALIAS_MAP = _build_alias_map()


def split_card_input(text: str) -> list[str]:
    normalized = text.strip()
    normalized = re.sub(r"[\n;|/\\]+", ",", normalized)
    normalized = re.sub(r"\s+и\s+", ",", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+(?:а\s+)?(?:также|ещё|еще)\s+", ",", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(?<=\S)\s+(?=\d+[\.)]\s+)", ", ", normalized)

    parts: list[str] = []
    for chunk in normalized.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        chunk = re.sub(r"^\d+[\.)]\s*", "", chunk)
        chunk = re.sub(r"^(?:прошлое|настоящее|будущее)\s*[:—\-]?\s*", "", chunk, flags=re.IGNORECASE)
        if chunk:
            parts.append(chunk)
    return parts


def _parse_minor_arcana(part: str) -> str | None:
    norm = normalize_card_text(part)
    for rank, words in RANK_WORDS.items():
        for rank_word in words:
            for suit_word, suit in SUIT_WORDS.items():
                patterns = [
                    f"{rank_word} {suit_word}",
                    f"{rank_word} of {suit_word}",
                    f"{suit_word} {rank_word}",
                ]
                for pattern in patterns:
                    if norm == normalize_card_text(pattern) or norm.endswith(normalize_card_text(pattern)):
                        card_id = f"{suit}{rank:02d}"
                        if card_id in TAROT_CARDS:
                            return card_id
    return None


def parse_single_card(part: str) -> str | None:
    norm = normalize_card_text(part)
    if not norm:
        return None

    if norm in ALIAS_MAP:
        return ALIAS_MAP[norm]

    minor = _parse_minor_arcana(part)
    if minor:
        return minor

    for alias, card_id in ALIAS_MAP.items():
        if len(alias) >= 4 and (alias in norm or norm in alias):
            return card_id

    return None


def parse_cards_from_aliases(text: str) -> list[str] | None:
    parts = split_card_input(text)
    if not parts:
        return None

    card_ids: list[str] = []
    for part in parts:
        card_id = parse_single_card(part)
        if card_id and card_id not in card_ids:
            card_ids.append(card_id)

    if len(card_ids) == REQUIRED_CARD_COUNT:
        return card_ids
    return None


def _build_card_catalog() -> str:
    lines = []
    for card_id, info in TAROT_CARDS.items():
        lines.append(f"{card_id} — {info['name']}")
    return "\n".join(lines)


def _extract_json_array(text: str) -> list | None:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r"\[[^\]]+\]", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        return None
    return None


def validate_card_ids(card_ids: list[str | None]) -> list[str] | None:
    if len(card_ids) != REQUIRED_CARD_COUNT:
        return None
    result: list[str] = []
    for card_id in card_ids:
        if not card_id or card_id not in TAROT_CARDS:
            return None
        if card_id in result:
            return None
        result.append(card_id)
    return result


async def parse_cards_with_llm(
    text: str,
    call_llm: Callable[[str, str], Awaitable[str]],
) -> list[str] | None:
    user_prompt = CARD_PARSE_USER_TEMPLATE.format(
        text=text,
        catalog=_build_card_catalog(),
    )
    try:
        raw = await call_llm(user_prompt, CARD_PARSE_SYSTEM_PROMPT)
    except Exception as exc:
        logging.error(f"LLM card parse failed: {exc}", exc_info=True)
        return None

    parsed = _extract_json_array(raw)
    if not parsed:
        return None

    return validate_card_ids([item if isinstance(item, str) else None for item in parsed])


async def parse_cards_from_text(
    text: str,
    call_llm: Callable[[str, str], Awaitable[str]] | None = None,
) -> tuple[list[str] | None, str]:
    """
    Распознать 3 карты из текста.
    Возвращает (card_ids, source) где source: 'alias' | 'llm' | 'failed'.
    """
    alias_result = parse_cards_from_aliases(text)
    if alias_result:
        return alias_result, "alias"

    if call_llm is None:
        return None, "failed"

    llm_result = await parse_cards_with_llm(text, call_llm)
    if llm_result:
        return llm_result, "llm"

    return None, "failed"


def format_parsed_cards(card_ids: list[str]) -> str:
    names = [get_card_info(cid)["name"] for cid in card_ids]
    return ", ".join(f"{i + 1}. {name}" for i, name in enumerate(names))
