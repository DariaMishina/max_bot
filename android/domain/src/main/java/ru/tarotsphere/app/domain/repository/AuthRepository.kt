package ru.tarotsphere.app.domain.repository

import ru.tarotsphere.app.domain.model.TokenPair

interface AuthRepository {
    fun hasAccessToken(): Boolean
    fun currentUserId(): String?
    suspend fun ensureGuestSession(): TokenPair
    suspend fun refreshSession(): TokenPair
}
