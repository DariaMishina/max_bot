package ru.tarotsphere.app.data.repository

import ru.tarotsphere.app.data.BuildConfig
import ru.tarotsphere.app.data.api.AppApi
import ru.tarotsphere.app.domain.model.Catalog
import ru.tarotsphere.app.domain.repository.CatalogRepository
import ru.tarotsphere.app.data.api.dto.RustoreVerifyRequestDto
import ru.tarotsphere.app.data.local.SecurePrefs
import ru.tarotsphere.app.domain.model.PaymentResult
import ru.tarotsphere.app.domain.model.PendingRustorePurchase

class CatalogRepositoryImpl(
    private val api: AppApi,
    private val prefs: SecurePrefs,
) : CatalogRepository {
    override suspend fun catalog(): Catalog = apiCall { api.catalog(includeTestContact = BuildConfig.DEBUG).toDomain() }
    override fun currentUserId(): String? = prefs.getUserId()
    override suspend fun verifyRustore(
        productId: String,
        purchaseId: String,
        invoiceId: String?,
        sandbox: Boolean,
    ): PaymentResult = apiCall {
        api.verifyRustore(RustoreVerifyRequestDto(productId, purchaseId, invoiceId, sandbox)).toDomain()
    }
    override fun pendingRustore(): PendingRustorePurchase? = prefs.pendingRustore()
    override fun savePendingRustore(purchase: PendingRustorePurchase) = prefs.savePendingRustore(purchase)
    override fun clearPendingRustore(purchaseId: String) = prefs.clearPendingRustore(purchaseId)
}
