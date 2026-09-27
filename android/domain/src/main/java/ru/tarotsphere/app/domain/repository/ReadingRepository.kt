package ru.tarotsphere.app.domain.repository

import ru.tarotsphere.app.domain.model.*

interface ReadingRepository {
    suspend fun deck(all: Boolean = false): List<TarotCard>
    suspend fun create(question: String, mode: CardSelectionMode, cardIds: List<String>?, requestId: String): Reading
    suspend fun detail(id: Long): Loaded<Reading>
    suspend fun followUp(reading: Reading, question: String, requestId: String): Reading
}
