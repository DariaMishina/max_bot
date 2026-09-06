package ru.tarotsphere.app.domain.repository

import ru.tarotsphere.app.domain.model.Balance
import ru.tarotsphere.app.domain.model.HistoryItem
import ru.tarotsphere.app.domain.model.UserProfile

interface UserRepository {
    suspend fun me(): UserProfile
    suspend fun balance(): Balance
    suspend fun history(): List<HistoryItem>
}
