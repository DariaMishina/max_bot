package ru.tarotsphere.app.domain.model

import java.time.LocalDateTime
import java.time.OffsetDateTime

data class Balance(
    val freeRemaining: Int,
    val paidRemaining: Int,
    val unlimitedUntil: String?,
    val totalUsed: Int,
) {
    val hasUnlimited: Boolean
        get() = unlimitedUntil?.let { value ->
            runCatching { OffsetDateTime.parse(value).toInstant().isAfter(java.time.Instant.now()) }
                .getOrElse { runCatching { LocalDateTime.parse(value).isAfter(LocalDateTime.now()) }.getOrDefault(false) }
        } ?: false

    val canDivinate: Boolean
        get() = freeRemaining > 0 || paidRemaining > 0 || hasUnlimited
}
