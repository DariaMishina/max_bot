package ru.tarotsphere.app.ui.components

import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

fun displayDate(value: String): String {
    val date = runCatching { OffsetDateTime.parse(value).toLocalDateTime() }
        .getOrElse { runCatching { LocalDateTime.parse(value) }.getOrNull() }
    return date?.format(DateTimeFormatter.ofPattern("d MMM yyyy, HH:mm", Locale.forLanguageTag("ru"))) ?: value
}
