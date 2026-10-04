"""Normalization and validation shared by the bot and the app API."""
from __future__ import annotations

import unicodedata


INVALID_QUESTION_MESSAGE = (
    "Сформулируйте вопрос или укажите тему словами. "
    "Например: «Что ждёт меня в работе?» или «Отношения»."
)


class InvalidQuestionError(ValueError):
    """Raised when text does not contain a meaningful question or topic."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def validate_question_text(value: str, *, max_length: int = 1000) -> str:
    """Return normalized text or reject punctuation, emoji and repeated noise."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = "".join(
        char for char in normalized
        if unicodedata.category(char) not in {"Cc", "Cf"}
    )
    normalized = " ".join(normalized.split())

    if not normalized:
        raise InvalidQuestionError("empty_question", "Вопрос не может быть пустым")
    if len(normalized) > max_length:
        raise InvalidQuestionError("long_question", f"Вопрос должен быть не длиннее {max_length} символов")

    words: list[str] = []
    current: list[str] = []
    for char in normalized:
        if char.isalpha():
            current.append(char)
        elif current:
            words.append("".join(current))
            current = []
    if current:
        words.append("".join(current))

    letters = [char.casefold() for word in words for char in word]
    if len(letters) < 3 or len(set(letters)) < 2 or not any(len(word) >= 3 for word in words):
        raise InvalidQuestionError("invalid_question", INVALID_QUESTION_MESSAGE)

    return normalized
