package ru.tarotsphere.app.domain.validation

import java.text.Normalizer

const val INVALID_QUESTION_MESSAGE =
    "Сформулируйте вопрос или укажите тему словами. Например: «Что ждёт меня в работе?» или «Отношения»."

fun normalizeQuestion(value: String): String = Normalizer.normalize(value, Normalizer.Form.NFKC)
    .filterNot { Character.getType(it) == Character.CONTROL.toInt() || Character.getType(it) == Character.FORMAT.toInt() }
    .trim()
    .replace(Regex("\\s+"), " ")

fun isMeaningfulQuestion(value: String): Boolean {
    val normalized = normalizeQuestion(value)
    val words = normalized.split(Regex("[^\\p{L}]+"))
        .filter { it.isNotEmpty() }
    val letters = words.flatMap { word -> word.map { it.lowercaseChar() } }
    return normalized.length <= 1000 &&
        letters.size >= 3 &&
        letters.toSet().size >= 2 &&
        words.any { it.length >= 3 }
}
