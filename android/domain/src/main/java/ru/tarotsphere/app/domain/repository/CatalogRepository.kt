package ru.tarotsphere.app.domain.repository

import ru.tarotsphere.app.domain.model.Catalog
import ru.tarotsphere.app.domain.model.PaymentResult
import ru.tarotsphere.app.domain.model.PendingRustorePurchase

interface CatalogRepository {
    suspend fun catalog(): Catalog
    fun currentUserId(): String?
    suspend fun verifyRustore(
        productId: String,
        purchaseId: String,
        invoiceId: String?,
        sandbox: Boolean,
    ): PaymentResult
    fun pendingRustore(): PendingRustorePurchase?
    fun savePendingRustore(purchase: PendingRustorePurchase)
    fun clearPendingRustore(purchaseId: String)
}
