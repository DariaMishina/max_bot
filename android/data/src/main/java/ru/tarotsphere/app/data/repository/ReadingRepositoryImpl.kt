package ru.tarotsphere.app.data.repository

import androidx.room.withTransaction
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import ru.tarotsphere.app.data.api.AppApi
import ru.tarotsphere.app.data.api.dto.*
import ru.tarotsphere.app.data.local.*
import ru.tarotsphere.app.domain.model.*
import ru.tarotsphere.app.domain.repository.ReadingRepository

class ReadingRepositoryImpl(
    private val api: AppApi, private val database: HistoryDatabase,
    private val prefs: SecurePrefs, private val json: Json,
) : ReadingRepository {
    private val dao = database.historyDao()
    override suspend fun deck() = apiCall { api.deck().cards.map { it.toDomain() } }
    override suspend fun create(question: String, cardIds: List<String>?, requestId: String): Reading = apiCall {
        val owner = prefs.getUserId().orEmpty()
        val dto = api.tarot(TarotRequestDto(question, if (cardIds == null) "random" else "manual", cardIds, requestId))
        cache(owner, dto)
        dto.toDomain()
    }
    override suspend fun detail(id: Long): Loaded<Reading> = apiCall {
        val owner = prefs.getUserId().orEmpty()
        try {
            val dto = api.detail(id)
            cache(owner, dto)
            Loaded(dto.toDomain())
        } catch (e: Exception) {
            val cached = if (e.allowsCache()) dao.detail(owner, id) else null
            if (cached == null) throw e
            Loaded(json.decodeFromString<ReadingDto>(cached.payload).toDomain(), fromCache = true)
        }
    }
    override suspend fun followUp(reading: Reading, question: String, requestId: String): Reading = apiCall {
        val owner = prefs.getUserId().orEmpty()
        val result = api.followUp(reading.id, FollowUpRequestDto(question, requestId))
        val dto = ReadingDto(
            id = reading.id, question = reading.question,
            cards = reading.cards.map { TarotCardDto(it.id, it.name, it.imageUrl) },
            interpretation = reading.interpretation, isFree = reading.isFree, createdAt = reading.createdAt,
            followUps = result.followUps, remaining = result.remaining,
        )
        cache(owner, dto)
        dto.toDomain()
    }
    private suspend fun cache(owner: String, dto: ReadingDto) {
        database.withTransaction {
            if (prefs.getUserId() == owner) {
                dao.saveDetail(ReadingEntity(owner, dto.readingId, json.encodeToString(dto)))
                dao.saveHistory(listOf(HistoryEntity(owner, dto.readingId, dto.question, "Таро", dto.createdAt, dto.isFree)))
            }
        }
    }
}
