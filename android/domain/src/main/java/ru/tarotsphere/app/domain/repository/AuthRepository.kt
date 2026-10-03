package ru.tarotsphere.app.domain.repository

import ru.tarotsphere.app.domain.model.TokenPair

interface AuthRepository {
    fun hasAccessToken(): Boolean
    fun currentUserId(): String?
    suspend fun restoreConfirmedSession(): Boolean
    suspend fun requestEmailCode(email: String)
    suspend fun confirmEmail(email: String, code: String): TokenPair
    suspend fun refreshSession(): TokenPair
}
