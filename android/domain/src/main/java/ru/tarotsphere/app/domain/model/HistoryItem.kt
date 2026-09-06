package ru.tarotsphere.app.domain.model

data class HistoryItem(
    val id: Long,
    val type: String,
    val question: String,
    val createdAt: String,
    val isFree: Boolean,
)
