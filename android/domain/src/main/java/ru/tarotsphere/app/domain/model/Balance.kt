package ru.tarotsphere.app.domain.model

data class Balance(
    val freeRemaining: Int,
    val paidRemaining: Int,
    val unlimitedUntil: String?,
    val totalUsed: Int,
) {
    val canDivinate: Boolean
        get() = freeRemaining > 0 || paidRemaining > 0 || !unlimitedUntil.isNullOrBlank()
}
