package ru.tarotsphere.app.data.repository

import retrofit2.HttpException
import ru.tarotsphere.app.data.api.AppApi
import ru.tarotsphere.app.data.api.dto.EmailConfirmRequestDto
import ru.tarotsphere.app.data.api.dto.EmailStartRequestDto
import ru.tarotsphere.app.data.api.dto.RefreshRequestDto
import ru.tarotsphere.app.data.api.dto.VkAuthRequestDto
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

    override suspend fun restoreConfirmedSession(): Boolean {
        val existing = prefs.getAccessToken()
        if (existing.isNullOrBlank()) return false
        return try {
            val confirmed = !authedApi.me().isGuest
            if (confirmed) prefs.markConfirmed()
            confirmed
        } catch (_: java.io.IOException) {
            // A confirmed account can still open its cached data offline.
            prefs.isConfirmedAccount()
        } catch (e: HttpException) {
            when {
                e.code() == 401 || e.code() == 403 -> false
                e.code() >= 500 -> prefs.isConfirmedAccount()
                else -> throw e
            }
        }
    }

    override suspend fun requestEmailCode(email: String) = apiCall {
        publicApi.emailStart(EmailStartRequestDto(email.trim(), prefs.deviceSignal()))
        Unit
    }

    override suspend fun confirmEmail(email: String, code: String): TokenPair = apiCall {
        // authedApi includes the old guest token when upgrading a staging user,
        // and works without a token on a clean installation.
        val tokens = authedApi.emailConfirm(
            EmailConfirmRequestDto(
                email.trim(), code.trim(), prefs.deviceSignal(), prefs.getRefreshToken(),
            ),
        ).toDomain()
        prefs.saveTokens(tokens.accessToken, tokens.refreshToken, tokens.userId)
        prefs.markConfirmed()
        tokens
    }

    override suspend fun confirmVk(accessToken: String): TokenPair = apiCall {
        val tokens = authedApi.vkAuth(
            VkAuthRequestDto(accessToken, prefs.deviceSignal(), prefs.getRefreshToken()),
        ).toDomain()
        prefs.saveTokens(tokens.accessToken, tokens.refreshToken, tokens.userId)
        prefs.markConfirmed()
        tokens
    }

    override suspend fun refreshSession(): TokenPair {
        val refresh = prefs.getRefreshToken()
            ?: throw IllegalStateException("Нет активной сессии")
        return try {
            val tokens = publicApi.refresh(RefreshRequestDto(refresh)).toDomain()
            prefs.saveTokens(tokens.accessToken, tokens.refreshToken, tokens.userId)
            tokens
        } catch (e: HttpException) {
            if (e.code() != 401) throw e
            prefs.clearTokens()
            throw e
        }
    }
}
