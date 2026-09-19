package ru.tarotsphere.app.domain.repository

import kotlinx.coroutines.flow.Flow
import ru.tarotsphere.app.domain.model.*

interface UserRepository {
    suspend fun me(): Loaded<UserProfile>
    suspend fun balance(): Balance
    fun observeHistory(): Flow<List<HistoryItem>>
    suspend fun refreshHistory(beforeId: Long? = null): Long?
    suspend fun feedback(message: String)
    suspend fun deleteData()
}
