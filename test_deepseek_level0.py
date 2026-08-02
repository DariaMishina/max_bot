"""
Уровень 0: локальная проверка DeepSeek API без бота и БД.

Запуск из корня проекта:
    python test_deepseek_level0.py
    python test_deepseek_level0.py --case tarot
    python test_deepseek_level0.py --case iching --case followup
    python test_deepseek_level0.py --case parse_aliases          # парсинг без API
    python test_deepseek_level0.py --case parse_llm --preview    # LLM-парсинг карт
    python test_deepseek_level0.py --case tarot_manual --preview # толкование по введённым картам
    python test_deepseek_level0.py --case tarot --preview   # только начало ответа
    python test_deepseek_level0.py --case tarot --output out  # сохранить в файлы
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import time
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

from handlers.divination import (
    DEEPSEEK_MAX_TOKENS,
    DEEPSEEK_MODEL,
    DEEPSEEK_TEMPERATURE,
    DEEPSEEK_URL,
    FOLLOW_UP_SYSTEM_PROMPT,
    ICHING_SYSTEM_PROMPT,
    ICHING_USER_INSTRUCTION,
    TAROT_SYSTEM_PROMPT,
    TAROT_USER_INSTRUCTION,
    format_interpretation_with_bold,
)
from handlers.hexagrams import get_hexagram_info
from handlers.tarot_cards import get_card_info
from handlers.tarot_card_parser import (
    format_parsed_cards,
    parse_cards_from_aliases,
    parse_cards_from_text,
    should_use_llm_fallback,
)

# Базовая линия до укорочения (прогон tarot 2026-06-13)
PREVIOUS_BASELINE = {"tarot_chars": 1599, "tarot_tokens": 724, "max_tokens": 650, "temperature": 0.65}

TAROT_CASE = {
    "name": "tarot",
    "question": "Что ждёт меня на работе в ближайший месяц?",
    "card_ids": ["Cups01", "Swords12", "Swords07"],
}

ICHING_CASE = {
    "name": "iching",
    "question": "Стоит ли мне менять работу в этом году?",
    "hexagram_id": "64",
}

FOLLOW_UP_CASE = {
    "name": "followup",
    "history": [
        {
            "role": "user",
            "content": "Мой вопрос: Что ждёт меня на работе в ближайший месяц?",
        },
        {
            "role": "assistant",
            "content": (
                "Расклад показывает период перемен: в прошлом — новые возможности, "
                "в настоящем — решительные действия, в будущем — осторожность с коллегами."
            ),
        },
        {
            "role": "user",
            "content": "А если я сейчас подам заявление на повышение — что скажут карты?",
        },
    ],
}

PARSE_ALIAS_CASES = [
    {
        "name": "comma_separated",
        "input": "Башня, Туз Кубков, Десятка Мечей",
        "expected": ["16-TheTower", "Cups01", "Swords10"],
    },
    {
        "name": "semicolon_and_positions",
        "input": "Прошлое: Дурак; Настоящее: Императрица; Будущее: Смерть",
        "expected": ["00-TheFool", "03-TheEmpress", "13-Death"],
    },
    {
        "name": "numbered_list",
        "input": "1. Семерка Мечей 2. Туз Жезлов 3. Король Пентаклей",
        "expected": ["Swords07", "Wands01", "Pentacles14"],
    },
    {
        "name": "cups_chashi",
        "input": "Башня, тройка чаш, десятка мечей",
        "expected": ["16-TheTower", "Cups03", "Swords10"],
    },
    {
        "name": "wands_posohi",
        "input": "фокусник, семерка посохов, дама шпаг",
        "expected": ["01-TheMagician", "Wands07", "Swords13"],
    },
    {
        "name": "pentacles_denarii",
        "input": "папесса, пятерка денариев, старец",
        "expected": ["02-TheHighPriestess", "Pentacles05", "09-TheHermit"],
    },
    {
        "name": "swords_klinki",
        "input": "правосудие, туз клинков, принцесса чаш",
        "expected": ["11-Justice", "Swords01", "Cups11"],
    },
    {
        "name": "space_separated",
        "input": "Башня семерка кубков повешенный",
        "expected": ["16-TheTower", "Cups07", "12-TheHangedMan"],
    },
    {
        "name": "typos_need_llm",
        "input": "Башння, Туз Кубков, 10 мечей",
        "expected": None,
    },
]

PARSE_LLM_CASE = {
    "name": "parse_llm",
    "input": "Башння, Туз Кубков, десятка мечей",
    "expected": ["16-TheTower", "Cups01", "Swords10"],
}

TAROT_MANUAL_CASE = {
    "name": "tarot_manual",
    "question": "Что ждёт меня на работе в ближайший месяц?",
    "cards_text": "Башня, Туз Кубков, Десятка Мечей",
    "expected_card_ids": ["16-TheTower", "Cups01", "Swords10"],
}

PARSE_FILTER_CASES = [
    {"name": "garbage", "input": "ываыва ываыва ываыва", "llm": False},
    {"name": "emoji", "input": "🔮🔮🔮", "llm": False},
    {"name": "too_short", "input": "xx", "llm": False},
    {"name": "typo_with_hints", "input": "Башння, Туз Кубков, десятка мечей", "llm": True},
    {"name": "normal", "input": "Башня, Туз Кубков, Десятка Мечей", "llm": True},
]

FORMAT_CASES = [
    {
        "name": "v4_title_and_sections",
        "input": (
            "**Толкование расклада «Работа»** **Прошлое:** Туз Кубков. "
            "**Настоящее:** Рыцарь Мечей. **Будущее:** Семёрка Мечей. "
            "**В целом:** месяц перемен."
        ),
        "must_contain": [
            "<b>Толкование расклада «Работа»</b>",
            "<b>Прошлое:</b>",
            "<b>Настоящее:</b>",
            "<b>Будущее:</b>",
            "<b>Общее толкование:</b>",
        ],
        "must_not_contain": ["**"],
    },
    {
        "name": "summary_aliases",
        "input": "Итог: всё сложится. Заключение: будьте терпеливы.",
        "must_contain": ["<b>Общее толкование</b>:"],
        "must_not_contain": ["**"],
    },
    {
        "name": "markdown_headers",
        "input": "# **Прошлое**: карта прошлого\n\n**Вывод:** итоговая интерпретация.",
        "must_contain": ["<b>Прошлое</b>", "<b>Общее толкование:</b>"],
        "must_not_contain": ["**"],
    },
]


def _load_api_key() -> str:
    load_dotenv()
    api_key = os.getenv("API_KEY", "").strip()
    if not api_key:
        print("Ошибка: API_KEY не найден в .env", file=sys.stderr)
        sys.exit(1)
    return api_key


def _build_tarot_user_prompt(question: str, card_ids: list[str]) -> str:
    cards_info = []
    positions = ["Прошлое", "Настоящее", "Будущее"]
    for i, card_id in enumerate(card_ids):
        card = get_card_info(card_id)
        cards_info.append(f"{positions[i]}: {card['name']} — {card['meaning']}")
    return (
        f"Вопрос пользователя: {question}\n\n"
        f"Выпавшие карты:\n" + "\n".join(cards_info) + "\n\n"
        f"{TAROT_USER_INSTRUCTION}"
    )


def _build_iching_user_prompt(question: str, hexagram_id: str) -> str:
    hexagram = get_hexagram_info(hexagram_id)
    return (
        f"Вопрос пользователя: {question}\n\n"
        f"Выпавшая гексаграмма: {hexagram['name']}\n"
        f"Значение гексаграммы: {hexagram['meaning']}\n\n"
        f"{ICHING_USER_INSTRUCTION}"
    )


async def _call_deepseek(
    session: aiohttp.ClientSession,
    api_key: str,
    *,
    system_prompt: str,
    messages: list[dict[str, str]],
) -> tuple[str, float, dict]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "max_tokens": DEEPSEEK_MAX_TOKENS,
        "temperature": DEEPSEEK_TEMPERATURE,
    }

    started = time.perf_counter()
    async with session.post(DEEPSEEK_URL, headers=headers, json=payload) as response:
        elapsed = time.perf_counter() - started
        body = await response.json(content_type=None)
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {body}")

        raw_text = body["choices"][0]["message"]["content"]
        formatted = format_interpretation_with_bold(raw_text)
        usage = body.get("usage", {})
        return formatted, elapsed, usage


def _preview(text: str, limit: int = 500) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def _check_bold_keywords(text: str) -> list[str]:
    found = []
    for keyword in ("Прошлое", "Настоящее", "Будущее", "Общее толкование"):
        if re.search(rf"<b>\s*{re.escape(keyword)}\s*:?\s*</b>", text, re.IGNORECASE):
            found.append(keyword)
    return found


def _print_response(
    case_name: str,
    text: str,
    *,
    preview_only: bool,
    output_dir: Path | None,
) -> None:
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{case_name}.txt"
        out_path.write_text(text, encoding="utf-8")
        print(f"Сохранено: {out_path}")

    if preview_only:
        print(f"Превью: {_preview(text)}")
        return

    print("--- Ответ ---")
    print(text)
    print("--- конец ответа ---")


async def run_parse_aliases(*, preview_only: bool, output_dir: Path | None) -> bool:
    print("\n=== Парсинг карт (алиасы, без API) ===")
    ok = True
    for case in PARSE_ALIAS_CASES:
        result = parse_cards_from_aliases(case["input"])
        case_ok = result == case["expected"]
        ok = ok and case_ok
        status = "PASS" if case_ok else "FAIL"
        print(f"{status}: {case['name']}")
        print(f"  ввод: {case['input']!r}")
        print(f"  ожидалось: {case['expected']}")
        print(f"  получено:  {result}")
        if result:
            print(f"  → {format_parsed_cards(result)}")
    return ok


async def run_parse_llm(
    session: aiohttp.ClientSession,
    api_key: str,
    *,
    preview_only: bool,
    output_dir: Path | None,
) -> bool:
    print("\n=== Парсинг карт (LLM fallback) ===")
    text = PARSE_LLM_CASE["input"]
    expected = PARSE_LLM_CASE["expected"]

    async def call_llm(user_prompt: str, system_prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 200,
            "temperature": 0.1,
        }
        async with session.post(DEEPSEEK_URL, headers=headers, json=payload) as response:
            body = await response.json(content_type=None)
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}: {body}")
            return body["choices"][0]["message"]["content"]

    started = time.perf_counter()
    try:
        card_ids, source = await parse_cards_from_text(text, call_llm=call_llm)
    except Exception as exc:
        print(f"FAIL: {exc}")
        return False
    elapsed = time.perf_counter() - started

    case_ok = card_ids == expected
    print(f"{'PASS' if case_ok else 'FAIL'}: {PARSE_LLM_CASE['name']} за {elapsed:.1f}s")
    print(f"  ввод: {text!r}")
    print(f"  source: {source}")
    print(f"  ожидалось: {expected}")
    print(f"  получено:  {card_ids}")
    if card_ids:
        print(f"  → {format_parsed_cards(card_ids)}")
    return case_ok


async def run_tarot_manual(
    session: aiohttp.ClientSession,
    api_key: str,
    *,
    preview_only: bool,
    output_dir: Path | None,
) -> bool:
    print("\n=== Таро (текстовый ввод карт) ===")
    cards_text = TAROT_MANUAL_CASE["cards_text"]
    expected = TAROT_MANUAL_CASE["expected_card_ids"]

    card_ids = parse_cards_from_aliases(cards_text)
    if card_ids != expected:
        print(f"FAIL: alias parse {card_ids} != {expected}")
        return False

    print(f"Карты: {format_parsed_cards(card_ids)}")
    user_prompt = _build_tarot_user_prompt(TAROT_MANUAL_CASE["question"], card_ids)
    try:
        text, elapsed, usage = await _call_deepseek(
            session,
            api_key,
            system_prompt=TAROT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as exc:
        print(f"FAIL: {exc}")
        return False

    bold = _check_bold_keywords(text)
    print(f"OK за {elapsed:.1f}s | tokens: {usage.get('total_tokens', '?')} | {len(text)} символов")
    print(f"Жирные заголовки: {bold or 'не найдены'}")
    _print_response("tarot_manual", text, preview_only=preview_only, output_dir=output_dir)
    return True


async def run_parse_filter(*, preview_only: bool, output_dir: Path | None) -> bool:
    print("\n=== Фильтр LLM (без API) ===")
    ok = True
    for case in PARSE_FILTER_CASES:
        result = should_use_llm_fallback(case["input"])
        case_ok = result == case["llm"]
        ok = ok and case_ok
        status = "PASS" if case_ok else "FAIL"
        print(f"{status}: {case['name']} → llm={result} (ожидалось {case['llm']})")
    return ok


async def run_format(*, preview_only: bool, output_dir: Path | None) -> bool:
    print("\n=== Форматирование ===")
    ok = True
    for case in FORMAT_CASES:
        result = format_interpretation_with_bold(case["input"])
        missing = [item for item in case["must_contain"] if item not in result]
        forbidden = [item for item in case.get("must_not_contain", []) if item in result]
        case_ok = not missing and not forbidden
        ok = ok and case_ok
        status = "PASS" if case_ok else "FAIL"
        print(f"{status}: {case['name']}")
        if missing:
            print(f"  нет в результате: {missing}")
        if forbidden:
            print(f"  лишнее в результате: {forbidden}")
        if preview_only or not case_ok:
            print(f"  → {_preview(result, limit=200)}")
        elif output_dir:
            _print_response(case["name"], result, preview_only=False, output_dir=output_dir)
    return ok


async def run_tarot(
    session: aiohttp.ClientSession,
    api_key: str,
    *,
    preview_only: bool,
    output_dir: Path | None,
) -> bool:
    print("\n=== Таро ===")
    user_prompt = _build_tarot_user_prompt(TAROT_CASE["question"], TAROT_CASE["card_ids"])
    try:
        text, elapsed, usage = await _call_deepseek(
            session,
            api_key,
            system_prompt=TAROT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as exc:
        print(f"FAIL: {exc}")
        return False

    bold = _check_bold_keywords(text)
    print(f"OK за {elapsed:.1f}s | tokens: {usage.get('total_tokens', '?')} | {len(text)} символов")
    print(
        "Сравнение с прошлым прогоном (tarot): "
        f"{PREVIOUS_BASELINE['tarot_chars']} → {len(text)} символов, "
        f"{PREVIOUS_BASELINE['tarot_tokens']} → {usage.get('total_tokens', '?')} токенов"
    )
    print(f"Жирные заголовки: {bold or 'не найдены'}")
    _print_response("tarot", text, preview_only=preview_only, output_dir=output_dir)
    return True


async def run_iching(
    session: aiohttp.ClientSession,
    api_key: str,
    *,
    preview_only: bool,
    output_dir: Path | None,
) -> bool:
    print("\n=== Ицзин ===")
    user_prompt = _build_iching_user_prompt(ICHING_CASE["question"], ICHING_CASE["hexagram_id"])
    try:
        text, elapsed, usage = await _call_deepseek(
            session,
            api_key,
            system_prompt=ICHING_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as exc:
        print(f"FAIL: {exc}")
        return False

    print(f"OK за {elapsed:.1f}s | tokens: {usage.get('total_tokens', '?')} | {len(text)} символов")
    _print_response("iching", text, preview_only=preview_only, output_dir=output_dir)
    return bool(text.strip())


async def run_followup(
    session: aiohttp.ClientSession,
    api_key: str,
    *,
    preview_only: bool,
    output_dir: Path | None,
) -> bool:
    print("\n=== Уточняющий вопрос ===")
    try:
        text, elapsed, usage = await _call_deepseek(
            session,
            api_key,
            system_prompt=FOLLOW_UP_SYSTEM_PROMPT,
            messages=FOLLOW_UP_CASE["history"],
        )
    except Exception as exc:
        print(f"FAIL: {exc}")
        return False

    print(f"OK за {elapsed:.1f}s | tokens: {usage.get('total_tokens', '?')} | {len(text)} символов")
    _print_response("followup", text, preview_only=preview_only, output_dir=output_dir)
    return bool(text.strip())


async def main(
    selected_cases: list[str] | None,
    *,
    preview_only: bool,
    output_dir: Path | None,
) -> int:
    api_key = _load_api_key()
    runners = {
        "format": lambda session, api_key, **kwargs: run_format(**kwargs),
        "parse_aliases": lambda session, api_key, **kwargs: run_parse_aliases(**kwargs),
        "parse_filter": lambda session, api_key, **kwargs: run_parse_filter(**kwargs),
        "parse_llm": run_parse_llm,
        "tarot_manual": run_tarot_manual,
        "tarot": run_tarot,
        "iching": run_iching,
        "followup": run_followup,
    }
    cases = selected_cases or list(runners.keys())

    unknown = [case for case in cases if case not in runners]
    if unknown:
        print(f"Неизвестные кейсы: {', '.join(unknown)}", file=sys.stderr)
        return 2

    print("DeepSeek level-0 test")
    print(
        f"model={DEEPSEEK_MODEL} max_tokens={DEEPSEEK_MAX_TOKENS} "
        f"temperature={DEEPSEEK_TEMPERATURE} "
        f"(было: max_tokens={PREVIOUS_BASELINE['max_tokens']}, "
        f"temperature={PREVIOUS_BASELINE['temperature']})"
    )

    results: dict[str, bool] = {}
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for case in cases:
            if case in ("format", "parse_aliases", "parse_filter"):
                results[case] = await runners[case](
                    session,
                    api_key,
                    preview_only=preview_only,
                    output_dir=output_dir,
                )
                continue
            results[case] = await runners[case](
                session,
                api_key,
                preview_only=preview_only,
                output_dir=output_dir,
            )

    print("\n=== Итог ===")
    for case, ok in results.items():
        print(f"{'PASS' if ok else 'FAIL'}: {case}")

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Локальный smoke-test DeepSeek для max_bot")
    parser.add_argument(
        "--case",
        action="append",
        choices=["format", "parse_aliases", "parse_filter", "parse_llm", "tarot_manual", "tarot", "iching", "followup"],
        help="Запустить только выбранный сценарий (можно указать несколько раз)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Показать только начало ответа (~500 символов), не полный текст",
    )
    parser.add_argument(
        "--output",
        metavar="DIR",
        help="Дополнительно сохранить полные ответы в файлы DIR/<case>.txt",
    )
    args = parser.parse_args()
    output_dir = Path(args.output) if args.output else None
    raise SystemExit(asyncio.run(main(args.case, preview_only=args.preview, output_dir=output_dir)))
