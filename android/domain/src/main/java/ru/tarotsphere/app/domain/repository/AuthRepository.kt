package ru.tarotsphere.app.domain.repository

import ru.tarotsphere.app.domain.model.TokenPair

interface AuthRepository {
    suspend fun recoveryStart(binding: Boolean, login: String, email: String, password: String): String
    suspend fun recoveryConfirm(binding: Boolean, challengeId: String, code: String, password: String)
    fun hasAccessToken(): Boolean
    fun currentUserId(): String?
    suspend fun restoreConfirmedSession(): Boolean
    suspend fun requestEmailCode(email: String)
    suspend fun confirmEmail(email: String, code: String): TokenPair
    suspend fun confirmVk(accessToken: String): TokenPair
    suspend fun authenticatePassword(login: String, password: String, registering: Boolean): TokenPair
    suspend fun refreshSession(): TokenPair
}
