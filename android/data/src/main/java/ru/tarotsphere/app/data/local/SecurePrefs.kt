package ru.tarotsphere.app.data.local

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.util.UUID

class SecurePrefs(context: Context) {
    private val appContext = context.applicationContext
    private val securePrefs: SharedPreferences by lazy(LazyThreadSafetyMode.SYNCHRONIZED) {
        createSecurePrefs(appContext)
    }
    private val metadataPrefs: SharedPreferences =
        appContext.getSharedPreferences(FILE_NAME_METADATA, Context.MODE_PRIVATE)

    fun getAccessToken(): String? = securePrefs.getString(KEY_ACCESS, null)
    fun getRefreshToken(): String? = securePrefs.getString(KEY_REFRESH, null)
    fun getUserId(): String? = securePrefs.getString(KEY_USER_ID, null)

    fun saveTokens(access: String, refresh: String, userId: String) {
        securePrefs.edit()
            .putString(KEY_ACCESS, access)
            .putString(KEY_REFRESH, refresh)
            .putString(KEY_USER_ID, userId)
            .apply()
    }

    fun clearTokens() {
        securePrefs.edit()
            .remove(KEY_ACCESS)
            .remove(KEY_REFRESH)
            .remove(KEY_USER_ID)
            .apply()
    }

    fun installId(): String {
        val existing = securePrefs.getString(KEY_INSTALL, null)
        if (!existing.isNullOrBlank()) return existing
        val created = UUID.randomUUID().toString()
        securePrefs.edit().putString(KEY_INSTALL, created).apply()
        return created
    }

    fun isOnboardingCompleted(): Boolean = metadataPrefs.getBoolean(KEY_ONBOARDING, false)

    fun markOnboardingCompleted() {
        metadataPrefs.edit().putBoolean(KEY_ONBOARDING, true).apply()
    }

    private fun createSecurePrefs(context: Context): SharedPreferences {
        try {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()
            return EncryptedSharedPreferences.create(
                context,
                FILE_NAME,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            )
        } catch (e: Exception) {
            Log.e(TAG, "Encrypted token storage is unavailable", e)
            throw IllegalStateException("Не удалось открыть защищённое хранилище", e)
        }
    }

    private companion object {
        const val TAG = "SecurePrefs"
        const val FILE_NAME = "tarot_sphere_secure"
        const val FILE_NAME_METADATA = "tarot_sphere_metadata"
        const val KEY_ACCESS = "access_token"
        const val KEY_REFRESH = "refresh_token"
        const val KEY_USER_ID = "user_id"
        const val KEY_INSTALL = "install_id"
        const val KEY_ONBOARDING = "onboarding_done"
    }
}
