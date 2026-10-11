package ru.tarotsphere.app.domain.model

data class CatalogPackage(
    val id: String,
    val rustoreProductId: String,
    val name: String,
    val priceRub: Int,
    val isSubscription: Boolean,
)

data class Catalog(
    val packages: List<CatalogPackage>,
    val paymentMethods: List<String>,
    val consultations: List<CatalogPackage> = emptyList(),
    val tarologistUrl: String? = null,
    val billingEnabled: Boolean = false,
    val rustoreSandbox: Boolean = true,
)

data class PaymentResult(
    val granted: Boolean,
    val balance: Balance,
)

data class PendingRustorePurchase(
    val userId: String,
    val productId: String,
    val purchaseId: String,
    val invoiceId: String?,
    val sandbox: Boolean,
)
