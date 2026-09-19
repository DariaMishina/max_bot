package ru.tarotsphere.app.data.api

import kotlinx.coroutines.runBlocking
import okhttp3.Authenticator
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import retrofit2.HttpException
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
                if (!prefs.replaceTokens(refresh, tokens.accessToken, tokens.refreshToken, tokens.userId)) return null
                response.request.newBuilder()
                    .header("Authorization", "Bearer ${tokens.accessToken}")
                    .build()
            } catch (e: HttpException) {
                // Only an explicitly rejected refresh token ends the session.
                // Network errors and server failures must not orphan a guest.
                if (e.code() == 401) prefs.clearRejectedTokens(refresh)
                null
            } catch (_: Exception) {
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
