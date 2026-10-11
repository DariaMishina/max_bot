package ru.tarotsphere.app.ui

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import ru.tarotsphere.app.domain.model.Balance
import ru.tarotsphere.app.domain.model.Catalog
import ru.tarotsphere.app.domain.model.CatalogPackage
import ru.tarotsphere.app.domain.model.PaymentResult
import ru.tarotsphere.app.domain.model.PendingRustorePurchase
import ru.tarotsphere.app.domain.repository.CatalogRepository
import ru.tarotsphere.app.ui.shop.PurchaseLauncher
import ru.tarotsphere.app.ui.shop.RuStorePurchaseProof
import ru.tarotsphere.app.ui.shop.ShopViewModel

@OptIn(ExperimentalCoroutinesApi::class)
class ShopViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @Before fun setup() = Dispatchers.setMain(dispatcher)
    @After fun teardown() = Dispatchers.resetMain()

    @Test fun verifiedPurchaseIsAcknowledgedAndCannotBeDoubleStarted() = runTest(dispatcher) {
        val repository = FakeCatalogRepository()
        val launcher = FakePurchaseLauncher()
        val model = ShopViewModel(repository, launcher)
        runCurrent()

        model.buy("3_spreads")
        model.buy("3_spreads")
        assertEquals(1, launcher.starts)
        launcher.complete(Result.success(RuStorePurchaseProof("purchase-1", "invoice-1", true)))
        runCurrent()

        assertEquals("purchase-1", repository.verifiedPurchase)
        assertEquals(listOf("purchase-1"), launcher.acknowledged)
        assertNull(model.state.value.purchasingId)
        assertTrue(model.state.value.paymentMessage!!.contains("пополнен"))
    }
}

private class FakeCatalogRepository : CatalogRepository {
    var verifiedPurchase: String? = null
    var pending: PendingRustorePurchase? = null
    private val item = CatalogPackage("3_spreads", "3_spreads", "3 расклада", 99, false)
    override suspend fun catalog() = Catalog(listOf(item), listOf("rustore"), billingEnabled = true)
    override fun currentUserId() = "user-1"
    override suspend fun verifyRustore(productId: String, purchaseId: String, invoiceId: String?, sandbox: Boolean): PaymentResult {
        verifiedPurchase = purchaseId
        return PaymentResult(true, Balance(0, 3, null, 0))
    }
    override fun pendingRustore() = pending
    override fun savePendingRustore(purchase: PendingRustorePurchase) { pending = purchase }
    override fun clearPendingRustore(purchaseId: String) { if (pending?.purchaseId == purchaseId) pending = null }
}

private class FakePurchaseLauncher : PurchaseLauncher {
    var starts = 0
    val acknowledged = mutableListOf<String>()
    private var callback: ((Result<RuStorePurchaseProof>) -> Unit)? = null
    override fun purchase(productId: String, appUserId: String, result: (Result<RuStorePurchaseProof>) -> Unit) {
        starts++
        callback = result
    }
    fun complete(result: Result<RuStorePurchaseProof>) = callback!!.invoke(result)
    override fun acknowledge(purchaseId: String) { acknowledged += purchaseId }
}
