package ru.tarotsphere.app.data.repository

import ru.tarotsphere.app.data.api.AppApi
import ru.tarotsphere.app.domain.model.Balance
import ru.tarotsphere.app.domain.model.HistoryItem
import ru.tarotsphere.app.domain.model.UserProfile
import ru.tarotsphere.app.domain.repository.UserRepository

class UserRepositoryImpl(
    private val api: AppApi,
) : UserRepository {
    override suspend fun me(): UserProfile = api.me().toDomain()

    override suspend fun balance(): Balance = api.balance().toDomain()

    override suspend fun history(): List<HistoryItem> = api.history().items.map { it.toDomain() }
}
