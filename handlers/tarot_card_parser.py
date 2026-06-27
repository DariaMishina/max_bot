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
MAX_CARDS_INPUT_ATTEMPTS = 3
MIN_INPUT_LENGTH = 3

RANK_WORDS: dict[int, list[str]] = {
    1: ["туз", "ace", "1", "as"],
    2: ["двойка", "2", "two"],
    3: ["тройка", "3", "three"],
    4: ["четверка", "4", "четв"],
    5: ["пятерка", "5", "пят"],
    6: ["шестерка", "6", "шест"],
    7: ["семерка", "7", "сем"],
    8: ["восьмерка", "8", "восьм"],
    9: ["девятка", "9", "девят"],
    10: ["десятка", "10", "десят"],
    11: ["паж", "page", "валет", "принцесса", "вестник", "служанка"],
    12: ["рыцарь", "knight", "принц", "кавалер", "всадник"],
    13: ["королева", "queen", "дама"],
    14: ["король", "king", "царь"],
}

SUIT_WORDS: dict[str, str] = {
    # Кубки / Чаши
    "кубков": "Cups",
    "кубки": "Cups",
    "кубок": "Cups",
    "чаш": "Cups",
    "чаши": "Cups",
    "чаша": "Cups",
    "чаше": "Cups",
    "cups": "Cups",
    "cup": "Cups",
    # Мечи / Клинки / Шпаги
    "мечи": "Swords",
    "меч": "Swords",
    "меча": "Swords",
    "клинков": "Swords",
    "клинки": "Swords",
    "клинок": "Swords",
    "шпаг": "Swords",
    "шпаги": "Swords",
    "шпага": "Swords",
    "swords": "Swords",
    "sword": "Swords",
    # Жезлы / Посохи / Скипетры
    "жезлов": "Wands",
    "жезлы": "Wands",
    "жезл": "Wands",
    "жезла": "Wands",
    "посохов": "Wands",
    "посохи": "Wands",
    "посох": "Wands",
    "посоха": "Wands",
    "скипетров": "Wands",
    "скипетры": "Wands",
    "скипетр": "Wands",
    "палок": "Wands",
    "палки": "Wands",
    "палка": "Wands",
    "дубин": "Wands",
    "дубины": "Wands",
    "дубина": "Wands",
    "булав": "Wands",
    "булавы": "Wands",
    "wands": "Wands",
    "wand": "Wands",
    "rods": "Wands",
    "staves": "Wands",
    # Пентакли / Монеты / Диски / Денарии
    "пентаклей": "Pentacles",
    "пентакли": "Pentacles",
    "пентакль": "Pentacles",
    "монет": "Pentacles",
    "монеты": "Pentacles",
    "монета": "Pentacles",
    "дисков": "Pentacles",
    "диски": "Pentacles",
    "диск": "Pentacles",
    "денариев": "Pentacles",
    "денарии": "Pentacles",
    "денарий": "Pentacles",
    "камней": "Pentacles",
    "камни": "Pentacles",
    "камень": "Pentacles",
    "pentacles": "Pentacles",
    "pentacle": "Pentacles",
    "coins": "Pentacles",
    "coin": "Pentacles",
    "discs": "Pentacles",
    "disc": "Pentacles",
}

# Старшие арканы: альтернативные названия из разных колод и школ
MAJOR_ALIASES: dict[str, str] = {
    "шут": "00-TheFool",
    "дурак": "00-TheFool",
    "fool": "00-TheFool",
    "маг": "01-TheMagician",
    "фокусник": "01-TheMagician",
    "волшебник": "01-TheMagician",
    "magician": "01-TheMagician",
    "жрица": "02-TheHighPriestess",
    "папесса": "02-TheHighPriestess",
    "верховная жрица": "02-TheHighPriestess",
    "верховная папесса": "02-TheHighPriestess",
    "императрица": "03-TheEmpress",
    "empress": "03-TheEmpress",
    "император": "04-TheEmperor",
    "царь": "04-TheEmperor",
    "emperor": "04-TheEmperor",
    "иерофант": "05-TheHierophant",
    "папа": "05-TheHierophant",
    "жрец": "05-TheHierophant",
    "первосвященник": "05-TheHierophant",
    "hierophant": "05-TheHierophant",
    "влюбленные": "06-TheLovers",
    "любовники": "06-TheLovers",
    "lovers": "06-TheLovers",
    "колесница": "07-TheChariot",
    "колесничий": "07-TheChariot",
    "возничий": "07-TheChariot",
    "chariot": "07-TheChariot",
    "сила": "08-Strength",
    "strength": "08-Strength",
    "отшельник": "09-TheHermit",
    "старец": "09-TheHermit",
    "старик": "09-TheHermit",
    "hermit": "09-TheHermit",
    "колесо фортуны": "10-WheelOfFortune",
    "колесо судьбы": "10-WheelOfFortune",
    "колесо": "10-WheelOfFortune",
    "фортуна": "10-WheelOfFortune",
    "wheel of fortune": "10-WheelOfFortune",
    "справедливость": "11-Justice",
    "правосудие": "11-Justice",
    "justice": "11-Justice",
    "повешенный": "12-TheHangedMan",
    "hanged man": "12-TheHangedMan",
    "смерть": "13-Death",
    "death": "13-Death",
    "умеренность": "14-Temperance",
    "воздержание": "14-Temperance",
    "алхимик": "14-Temperance",
    "temperance": "14-Temperance",
    "дьявол": "15-TheDevil",
    "devil": "15-TheDevil",
    "башня": "16-TheTower",
    "неудача": "16-TheTower",
    "tower": "16-TheTower",
    "the tower": "16-TheTower",
    "звезда": "17-TheStar",
    "star": "17-TheStar",
    "луна": "18-TheMoon",
    "moon": "18-TheMoon",
    "солнце": "19-TheSun",
    "sun": "19-TheSun",
    "суд": "20-Judgement",
    "судный день": "20-Judgement",
    "воскресение": "20-Judgement",
    "judgement": "20-Judgement",
    "judgment": "20-Judgement",
    "мир": "21-TheWorld",
    "world": "21-TheWorld",
}

CARD_PARSE_SYSTEM_PROMPT = (
    "Ты помощник таролога. Определи ровно 3 карты Таро Rider-Waite из текста пользователя "
    "в порядке слева направо (Прошлое, Настоящее, Будущее). "
    "Верни ТОЛЬКО JSON-массив из 3 строк — ID карт из списка ниже. "
    "Учитывай синонимы: чаши=кубки, посохи/скипетры=жезлы, монеты/диски/денарии=пентакли, "
    "клинки/шпаги=мечи, дама=королева, папесса=жрица, жрец/папа=иерофант, шут=дурак. "
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

    for alias, card_id in MAJOR_ALIASES.items():
        aliases[normalize_card_text(alias)] = card_id

    return aliases


ALIAS_MAP = _build_alias_map()


def _build_tarot_hint_words() -> frozenset[str]:
    hints: set[str] = set(SUIT_WORDS.keys())
    for words in RANK_WORDS.values():
        hints.update(w for w in words if len(w) >= 3)
    hints.update(
        word for alias in MAJOR_ALIASES
        for word in normalize_card_text(alias).split()
        if len(word) >= 3
    )
    return frozenset(hints)


TAROT_HINT_WORDS = _build_tarot_hint_words()


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


def count_identified_cards(text: str) -> int:
    """Сколько карт удалось распознать локально (0–3), без LLM."""
    parts = split_card_input(text)
    card_ids: list[str] = []
    for part in parts:
        card_id = parse_single_card(part)
        if card_id and card_id not in card_ids:
            card_ids.append(card_id)
    if len(card_ids) >= REQUIRED_CARD_COUNT:
        return REQUIRED_CARD_COUNT

    greedy = _parse_cards_greedy(text)
    if greedy:
        return len(greedy)
    return len(card_ids)


def should_use_llm_fallback(text: str) -> bool:
    """
    Есть ли смысл звать LLM: отсечь явный мусор без таро-лексики и без частичных совпадений.
    """
    stripped = text.strip()
    if len(stripped) < MIN_INPUT_LENGTH:
        return False

    norm = normalize_card_text(text)
    if not re.search(r"[a-zа-я]", norm, re.IGNORECASE):
        return False

    if count_identified_cards(text) >= 1:
        return True

    if any(hint in norm for hint in TAROT_HINT_WORDS):
        return True

    for alias in ALIAS_MAP:
        if len(alias) >= 4 and alias in norm:
            return True

    return False


def _parse_cards_greedy(text: str) -> list[str] | None:
    """Извлечь 3 карты из текста через пробелы (жадное сопоставление)."""
    remaining = normalize_card_text(text)
    if not remaining:
        return None

    found: list[str] = []
    aliases_by_len = sorted(ALIAS_MAP.items(), key=lambda item: len(item[0]), reverse=True)

    while remaining and len(found) < REQUIRED_CARD_COUNT:
        card_id = None
        matched_len = 0

        for alias, cid in aliases_by_len:
            if len(alias) < 2:
                continue
            if remaining == alias or remaining.startswith(f"{alias} "):
                card_id = cid
                matched_len = len(alias)
                break

        if not card_id:
            words = remaining.split()
            for end in range(min(len(words), 4), 0, -1):
                part = " ".join(words[:end])
                card_id = parse_single_card(part)
                if card_id:
                    matched_len = len(normalize_card_text(part))
                    break

        if not card_id:
            return None
        if card_id not in found:
            found.append(card_id)
        remaining = remaining[matched_len:].strip()

    return found if len(found) == REQUIRED_CARD_COUNT else None


def parse_cards_from_aliases(text: str) -> list[str] | None:
    parts = split_card_input(text)

    if len(parts) == 1 and " " in parts[0]:
        greedy = _parse_cards_greedy(text)
        if greedy:
            return greedy

    if not parts:
        return None

    card_ids: list[str] = []
    for part in parts:
        card_id = parse_single_card(part)
        if card_id and card_id not in card_ids:
            card_ids.append(card_id)

    if len(card_ids) == REQUIRED_CARD_COUNT:
        return card_ids

    greedy = _parse_cards_greedy(text)
    if greedy:
        return greedy
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
    Возвращает (card_ids, source) где source: 'alias' | 'llm' | 'rejected' | 'failed'.
    """
    alias_result = parse_cards_from_aliases(text)
    if alias_result:
        return alias_result, "alias"

    if call_llm is None:
        return None, "failed"

    if not should_use_llm_fallback(text):
        return None, "rejected"

    llm_result = await parse_cards_with_llm(text, call_llm)
    if llm_result:
        return llm_result, "llm"

    return None, "failed"


def format_parsed_cards(card_ids: list[str]) -> str:
    names = [get_card_info(cid)["name"] for cid in card_ids]
    return ", ".join(f"{i + 1}. {name}" for i, name in enumerate(names))
