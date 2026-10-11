package ru.tarotsphere.app.data.local

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import android.provider.Settings
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.util.UUID
import ru.tarotsphere.app.domain.model.PendingRustorePurchase

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
    fun isConfirmedAccount(): Boolean = securePrefs.getBoolean(KEY_CONFIRMED, false)
    fun pendingRustore(): PendingRustorePurchase? {
        val userId = securePrefs.getString(KEY_PENDING_USER, null) ?: return null
        if (userId != getUserId()) return null
        val productId = securePrefs.getString(KEY_PENDING_PRODUCT, null) ?: return null
        val purchaseId = securePrefs.getString(KEY_PENDING_PURCHASE, null) ?: return null
        return PendingRustorePurchase(
            userId = userId,
            productId = productId,
            purchaseId = purchaseId,
            invoiceId = securePrefs.getString(KEY_PENDING_INVOICE, null),
            sandbox = securePrefs.getBoolean(KEY_PENDING_SANDBOX, true),
        )
    }

    fun savePendingRustore(purchase: PendingRustorePurchase) {
        securePrefs.edit()
            .putString(KEY_PENDING_USER, purchase.userId)
            .putString(KEY_PENDING_PRODUCT, purchase.productId)
            .putString(KEY_PENDING_PURCHASE, purchase.purchaseId)
            .putString(KEY_PENDING_INVOICE, purchase.invoiceId)
            .putBoolean(KEY_PENDING_SANDBOX, purchase.sandbox)
            .apply()
    }

    fun clearPendingRustore(purchaseId: String) {
        if (securePrefs.getString(KEY_PENDING_PURCHASE, null) != purchaseId) return
        securePrefs.edit()
            .remove(KEY_PENDING_PRODUCT)
            .remove(KEY_PENDING_USER)
            .remove(KEY_PENDING_PURCHASE)
            .remove(KEY_PENDING_INVOICE)
            .remove(KEY_PENDING_SANDBOX)
            .apply()
    }

    @Synchronized
    fun saveTokens(access: String, refresh: String, userId: String) {
        securePrefs.edit()
            .putString(KEY_ACCESS, access)
            .putString(KEY_REFRESH, refresh)
            .putString(KEY_USER_ID, userId)
            .apply()
    }

    @Synchronized
    fun markConfirmed() {
        securePrefs.edit().putBoolean(KEY_CONFIRMED, true).apply()
    }

    @Synchronized
    fun clearTokens() {
        securePrefs.edit()
            .remove(KEY_ACCESS)
            .remove(KEY_REFRESH)
            .remove(KEY_USER_ID)
            .remove(KEY_CONFIRMED)
            .apply()
    }

    @Synchronized
    fun replaceTokens(expectedRefresh: String, access: String, refresh: String, userId: String): Boolean {
        if (getRefreshToken() != expectedRefresh) return false
        saveTokens(access, refresh, userId)
        return true
    }

    @Synchronized
    fun clearRejectedTokens(expectedRefresh: String) {
        if (getRefreshToken() == expectedRefresh) clearTokens()
    }

    @Synchronized
    fun resetGuest() {
        check(securePrefs.edit().clear().commit()) { "Не удалось очистить сессию" }
        metadataPrefs.edit().clear().commit()
    }

    fun installId(): String {
        val existing = securePrefs.getString(KEY_INSTALL, null)
        if (!existing.isNullOrBlank()) return existing
        val created = UUID.randomUUID().toString()
        securePrefs.edit().putString(KEY_INSTALL, created).apply()
        return created
    }

    fun deviceSignal(): String = Settings.Secure.getString(
        appContext.contentResolver,
        Settings.Secure.ANDROID_ID,
    ).orEmpty()

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
        const val KEY_CONFIRMED = "confirmed_account"
        const val KEY_INSTALL = "install_id"
        const val KEY_ONBOARDING = "onboarding_done"
        const val KEY_PENDING_PRODUCT = "pending_rustore_product"
        const val KEY_PENDING_USER = "pending_rustore_user"
        const val KEY_PENDING_PURCHASE = "pending_rustore_purchase"
        const val KEY_PENDING_INVOICE = "pending_rustore_invoice"
        const val KEY_PENDING_SANDBOX = "pending_rustore_sandbox"
    }
}
