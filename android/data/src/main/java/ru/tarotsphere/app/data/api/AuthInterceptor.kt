package ru.tarotsphere.app.data.api

import okhttp3.Interceptor
import okhttp3.Response
import ru.tarotsphere.app.data.local.SecurePrefs

class AuthInterceptor(
    private val prefs: SecurePrefs,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        val path = original.url.encodedPath
        if (path.endsWith("/v1/auth/guest") || path.endsWith("/v1/auth/refresh")) {
            return chain.proceed(original)
        }
        val token = prefs.getAccessToken() ?: return chain.proceed(original)
        val authed = original.newBuilder()
            .header("Authorization", "Bearer $token")
            .build()
        return chain.proceed(authed)
    }
}
