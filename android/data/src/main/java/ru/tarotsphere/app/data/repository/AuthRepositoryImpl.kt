package ru.tarotsphere.app.data.repository

import retrofit2.HttpException
import ru.tarotsphere.app.data.api.AppApi
import ru.tarotsphere.app.data.api.dto.GuestRequestDto
import ru.tarotsphere.app.data.api.dto.RefreshRequestDto
import ru.tarotsphere.app.data.local.SecurePrefs
import ru.tarotsphere.app.domain.model.TokenPair
import ru.tarotsphere.app.domain.repository.AuthRepository

class AuthRepositoryImpl(
    private val authedApi: AppApi,
    private val publicApi: AppApi,
    private val prefs: SecurePrefs,
) : AuthRepository {
    override fun hasAccessToken(): Boolean = !prefs.getAccessToken().isNullOrBlank()

    override fun currentUserId(): String? = prefs.getUserId()

    override suspend fun ensureGuestSession(): TokenPair {
        val existing = prefs.getAccessToken()
        if (!existing.isNullOrBlank()) {
            return try {
                val me = authedApi.me()
                TokenPair(
                    // The authenticator may have refreshed the pair while /me ran.
                    accessToken = prefs.getAccessToken().orEmpty(),
                    refreshToken = prefs.getRefreshToken().orEmpty(),
                    userId = me.userId,
                    expiresIn = 0,
                    balance = me.balance.toDomain(),
                )
            } catch (e: HttpException) {
                if (e.code() != 401) throw e

                // The authenticator clears tokens only when the refresh token is
                // explicitly rejected. On a transient refresh failure it keeps
                // them, so the user can retry without losing the guest session.
                if (prefs.getRefreshToken().isNullOrBlank()) createGuest() else throw e
            }
        }
        return createGuest()
    }

    override suspend fun refreshSession(): TokenPair {
        val refresh = prefs.getRefreshToken() ?: return createGuest()
        return try {
            val tokens = publicApi.refresh(RefreshRequestDto(refresh)).toDomain()
            prefs.saveTokens(tokens.accessToken, tokens.refreshToken, tokens.userId)
            tokens
        } catch (e: HttpException) {
            if (e.code() != 401) throw e
            prefs.clearTokens()
            createGuest()
        }
    }

    private suspend fun createGuest(): TokenPair {
        val tokens = publicApi.guest(GuestRequestDto(prefs.installId())).toDomain()
        prefs.saveTokens(tokens.accessToken, tokens.refreshToken, tokens.userId)
        return tokens
    }
}
