"""
Вызов DeepSeek для гаданий — без привязки к aiomax.
Используют app/divination_service.py и (позже) handlers бота.
"""
from __future__ import annotations

import logging
import re

import aiohttp

from main.config_reader import config

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_MAX_TOKENS = 1200
DEEPSEEK_TEMPERATURE = 0.65

TAROT_SYSTEM_PROMPT = (
    "Ты опытный таролог. Толкование расклада из 3 карт Таро: "
    "1-я — Прошлое, 2-я — Настоящее, 3-я — Будущее. "
    "Отвечай на русском, мудро и по существу. "
    "Формат: заголовки «Прошлое:», «Настоящее:», «Будущее:», «Общее толкование:» — "
    "по 2–3 предложения на каждую карту, затем общее толкование на 3–4 предложения. "
    "Всего 4–6 абзацев, без markdown и списков."
)

TAROT_USER_INSTRUCTION = "Дай толкование этого расклада в контексте вопроса пользователя."


def format_interpretation_with_bold(text: str) -> str:
    """Форматирует текст толкования для HTML (как в handlers/divination.py)."""
    section_aliases = [
        (re.compile(r"карта\s+прошлого", re.IGNORECASE), "Прошлое"),
        (re.compile(r"^прошлое\b", re.IGNORECASE), "Прошлое"),
        (re.compile(r"карта\s+настоящего", re.IGNORECASE), "Настоящее"),
        (re.compile(r"^настоящее\b", re.IGNORECASE), "Настоящее"),
        (re.compile(r"карта\s+будущего", re.IGNORECASE), "Будущее"),
        (re.compile(r"^будущее\b", re.IGNORECASE), "Будущее"),
        (re.compile(r"итоговая\s+интерпретация", re.IGNORECASE), "Общее толкование"),
        (re.compile(r"общее\s+толкование", re.IGNORECASE), "Общее толкование"),
        (re.compile(r"^итог\b", re.IGNORECASE), "Общее толкование"),
        (re.compile(r"^заключение\b", re.IGNORECASE), "Общее толкование"),
        (re.compile(r"^в\s+целом\b", re.IGNORECASE), "Общее толкование"),
        (re.compile(r"^вывод\b", re.IGNORECASE), "Общее толкование"),
        (re.compile(r"^общий\s+вывод\b", re.IGNORECASE), "Общее толкование"),
        (re.compile(r"^резюме\b", re.IGNORECASE), "Общее толкование"),
    ]
    keywords = ["Прошлое", "Настоящее", "Будущее", "Общее толкование"]
    summary_markdown = re.compile(
        r"\*\*(?:Общее\s+толкование|Итог(?:овое\s+толкование)?|Заключение|"
        r"В\s+целом|Вывод|Общий\s+вывод|Резюме)\s*:?\*\*",
        re.IGNORECASE,
    )
    summary_plain = re.compile(
        r"(?<![\w>])(?:Итог(?:овое\s+толкование)?|Заключение|В\s+целом|"
        r"Вывод|Общий\s+вывод|Резюме)(\s*[:—\-])",
        re.IGNORECASE,
    )

    def _section_label(title: str) -> str | None:
        clean = re.sub(r"\*+", "", title).strip()
        for pattern, label in section_aliases:
            if pattern.search(clean):
                return label
        return None

    def _format_header_line(line: str) -> str:
        match = re.match(r"^(#{1,3})\s+(.+)$", line.strip())
        if not match:
            return line
        title = re.sub(r"\*+", "", match.group(2)).strip()
        parts = re.match(r"^(.+?)(\s*[:—\-]\s*.+)?$", title)
        if not parts:
            return line
        main_part = parts.group(1).strip()
        suffix = parts.group(2) or ""
        label = _section_label(main_part)
        if label:
            return f"<b>{label}</b>{suffix}"
        if len(match.group(1)) == 1:
            return f"<b>{main_part}</b>{suffix}"
        return f"<b>{main_part}</b>{suffix}"

    def _normalize_summary_headers(line: str) -> str:
        line = summary_markdown.sub("<b>Общее толкование:</b>", line)
        return summary_plain.sub(r"<b>Общее толкование</b>\1", line)

    def _markdown_bold_to_html(line: str) -> str:
        return re.sub(r"\*\*([^*]+?)\*\*", r"<b>\1</b>", line)

    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            lines.append(_format_header_line(stripped))
            continue
        formatted_line = line
        for keyword in keywords:
            formatted_line = re.sub(
                rf"\*\*({re.escape(keyword)})\s*:([^*]*)\*\*",
                rf"<b>\1:</b>\2",
                formatted_line,
                flags=re.IGNORECASE,
            )
            formatted_line = re.sub(
                rf"\*\*({re.escape(keyword)})\s*:\*\*",
                rf"<b>\1:</b>",
                formatted_line,
                flags=re.IGNORECASE,
            )
            formatted_line = re.sub(
                rf"\*\*({re.escape(keyword)})\*\*(\s*[:—\-]?)",
                rf"<b>\1</b>\2",
                formatted_line,
                flags=re.IGNORECASE,
            )
            if re.search(rf"<b>\s*{re.escape(keyword)}\s*</b>", formatted_line, re.IGNORECASE):
                continue
            formatted_line = re.sub(
                rf"(^|\n)({re.escape(keyword)})(\s*[:—\-])",
                rf"\1<b>\2</b>\3",
                formatted_line,
                flags=re.IGNORECASE,
            )
        formatted_line = _normalize_summary_headers(formatted_line)
        formatted_line = _markdown_bold_to_html(formatted_line)
        lines.append(formatted_line)
    return "\n".join(lines)


async def call_deepseek(
    messages: list,
    system_prompt: str,
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    format_output: bool = True,
) -> str:
    api_key = config.api_key.get_secret_value()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "max_tokens": max_tokens if max_tokens is not None else DEEPSEEK_MAX_TOKENS,
        "temperature": temperature if temperature is not None else DEEPSEEK_TEMPERATURE,
    }
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as session:
        async with session.post(DEEPSEEK_URL, headers=headers, json=payload) as response:
            if response.status == 200:
                result = await response.json()
                text = result["choices"][0]["message"]["content"]
                if format_output:
                    return format_interpretation_with_bold(text)
                return text
            error_text = await response.text()
            logging.error("DeepSeek API error: %s - %s", response.status, error_text)
            raise RuntimeError(f"DeepSeek API error: {response.status}")


async def interpret_tarot_with_llm(question: str, card_ids: list[str]) -> str:
    from handlers.tarot_cards import get_card_info

    positions = ["Прошлое", "Настоящее", "Будущее"]
    cards_info = []
    for i, card_id in enumerate(card_ids):
        card = get_card_info(card_id)
        cards_info.append(f"{positions[i]}: {card['name']} — {card['meaning']}")

    user_prompt = (
        f"Вопрос пользователя: {question}\n\n"
        f"Выпавшие карты:\n" + "\n".join(cards_info) + "\n\n"
        f"{TAROT_USER_INSTRUCTION}"
    )
    return await call_deepseek(
        [{"role": "user", "content": user_prompt}],
        TAROT_SYSTEM_PROMPT,
    )
