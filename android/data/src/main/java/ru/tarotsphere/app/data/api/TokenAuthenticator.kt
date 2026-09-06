package ru.tarotsphere.app.data.api

import kotlinx.coroutines.runBlocking
import okhttp3.Authenticator
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import ru.tarotsphere.app.data.api.dto.RefreshRequestDto
import ru.tarotsphere.app.data.local.SecurePrefs

class TokenAuthenticator(
    private val prefs: SecurePrefs,
    private val refreshApi: AppApi,
) : Authenticator {
    override fun authenticate(route: Route?, response: Response): Request? {
        if (responseCount(response) >= 2) return null
        val refresh = prefs.getRefreshToken() ?: return null
        synchronized(lock) {
            val currentAccess = prefs.getAccessToken()
            val failedAccess = response.request.header("Authorization")?.removePrefix("Bearer ")?.trim()
            if (!currentAccess.isNullOrBlank() && currentAccess != failedAccess) {
                return response.request.newBuilder()
                    .header("Authorization", "Bearer $currentAccess")
                    .build()
            }
            return try {
                val tokens = runBlocking {
                    refreshApi.refresh(RefreshRequestDto(refresh))
                }
                prefs.saveTokens(tokens.accessToken, tokens.refreshToken, tokens.userId)
                response.request.newBuilder()
                    .header("Authorization", "Bearer ${tokens.accessToken}")
                    .build()
            } catch (_: Exception) {
                prefs.clearTokens()
                null
            }
        }
    }

    private fun responseCount(response: Response): Int {
        var result = 1
        var prior = response.priorResponse
        while (prior != null) {
            result++
            prior = prior.priorResponse
        }
        return result
    }

    private companion object {
        val lock = Any()
    }
}
