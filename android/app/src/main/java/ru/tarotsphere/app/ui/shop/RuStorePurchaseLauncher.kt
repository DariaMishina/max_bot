package ru.tarotsphere.app.ui.shop

import ru.tarotsphere.app.BuildConfig

import ru.rustore.sdk.pay.RuStorePayClient
import ru.rustore.sdk.pay.model.AcknowledgementState
import ru.rustore.sdk.pay.model.AppUserId
import ru.rustore.sdk.pay.model.PreferredPurchaseType
import ru.rustore.sdk.pay.model.ProductId
import ru.rustore.sdk.pay.model.ProductPurchaseParams
import ru.rustore.sdk.pay.model.ProductType
import ru.rustore.sdk.pay.model.PurchaseId
import ru.rustore.sdk.pay.model.SdkTheme

data class RuStorePurchaseProof(
    val purchaseId: String,
    val invoiceId: String?,
    val sandbox: Boolean,
)

interface PurchaseLauncher {
    fun purchase(productId: String, appUserId: String, result: (Result<RuStorePurchaseProof>) -> Unit)
    fun acknowledge(purchaseId: String)
}

class RuStorePurchaseLauncher : PurchaseLauncher {
    private val purchases get() = RuStorePayClient.instance.getPurchaseInteractor()

    override fun purchase(
        productId: String,
        appUserId: String,
        result: (Result<RuStorePurchaseProof>) -> Unit,
    ) {
        if (!BuildConfig.RUSTORE_BILLING_CONFIGURED) {
            result(Result.failure(IllegalStateException("Покупки недоступны в локальной тестовой сборке")))
            return
        }
        val params = ProductPurchaseParams(
            productId = ProductId(productId),
            appUserId = AppUserId(appUserId),
        )
        purchases.purchase(
            params = params,
            preferredPurchaseType = PreferredPurchaseType.ONE_STEP,
            sdkTheme = SdkTheme.LIGHT,
        ).addOnSuccessListener { purchase ->
            result(Result.success(RuStorePurchaseProof(
                purchaseId = purchase.purchaseId.value,
                invoiceId = if (purchase.productType == ProductType.SUBSCRIPTION) null else purchase.invoiceId.value,
                sandbox = purchase.sandbox,
            )))
        }.addOnFailureListener { error ->
            result(Result.failure(error))
        }
    }

    override fun acknowledge(purchaseId: String) {
        if (!BuildConfig.RUSTORE_BILLING_CONFIGURED) return
        purchases.updateAcknowledgementState(
            purchaseId = PurchaseId(purchaseId),
            state = AcknowledgementState.ACKNOWLEDGED,
            developerPayload = null,
        )
    }
}
