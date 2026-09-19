package ru.tarotsphere.app.data.repository

import androidx.room.withTransaction
import kotlinx.coroutines.flow.map
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import ru.tarotsphere.app.data.api.AppApi
import ru.tarotsphere.app.data.api.dto.*
import ru.tarotsphere.app.data.local.*
import ru.tarotsphere.app.domain.model.*
import ru.tarotsphere.app.domain.repository.UserRepository

class UserRepositoryImpl(
    private val api: AppApi, private val database: HistoryDatabase,
    private val prefs: SecurePrefs, private val json: Json,
) : UserRepository {
    private val dao = database.historyDao()
    override suspend fun me(): Loaded<UserProfile> = apiCall {
        val owner = prefs.getUserId().orEmpty()
        try {
            val dto = api.me()
            database.withTransaction {
                if (prefs.getUserId() == owner) dao.saveProfile(ProfileEntity(owner, json.encodeToString(dto)))
            }
            Loaded(dto.toDomain())
        } catch (e: Exception) {
            val cached = if (e.allowsCache()) dao.profile(owner) else null
            if (cached == null) throw e
            Loaded(json.decodeFromString<MeDto>(cached.payload).toDomain(), fromCache = true)
        }
    }
    override suspend fun balance(): Balance = apiCall { api.balance().toDomain() }
    override fun observeHistory() = dao.observe(prefs.getUserId().orEmpty()).map { rows -> rows.map { it.toDomain() } }
    override suspend fun refreshHistory(beforeId: Long?): Long? = apiCall {
        val owner = prefs.getUserId().orEmpty()
        val page = api.history(beforeId)
        database.withTransaction {
            if (prefs.getUserId() == owner) dao.saveHistory(page.items.map {
                HistoryEntity(owner, it.id, it.question, it.type, it.createdAt, it.isFree)
            })
        }
        page.nextBeforeId
    }
    override suspend fun feedback(message: String) = apiCall { api.feedback(FeedbackRequestDto(message.trim())) }
    override suspend fun deleteData() = apiCall {
        api.deleteMe()
        // Keep local data if the server rejected deletion. DELETE is safe to retry.
        prefs.resetGuest()
        dao.clear()
    }
}
