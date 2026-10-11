package ru.tarotsphere.app.ui.shop

import kotlinx.coroutines.CancellationException
import ru.tarotsphere.app.ui.components.userMessage
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import ru.tarotsphere.app.domain.model.Catalog
import ru.tarotsphere.app.domain.model.PendingRustorePurchase
import ru.tarotsphere.app.domain.repository.CatalogRepository

data class ShopUiState(
    val loading: Boolean = true,
    val catalog: Catalog? = null,
    val error: String? = null,
    val purchasingId: String? = null,
    val paymentMessage: String? = null,
    val canRetryVerification: Boolean = false,
)

class ShopViewModel(
    private val catalogRepository: CatalogRepository,
    private val purchaseLauncher: PurchaseLauncher,
) : ViewModel() {
    private val _state = MutableStateFlow(ShopUiState())
    val state: StateFlow<ShopUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        if (_state.value.loading && _state.value.catalog != null) return
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)
            try {
                _state.value = ShopUiState(loading = false, catalog = catalogRepository.catalog())
                resumePending()
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) {
                _state.value = ShopUiState(loading = false, error = e.userMessage())
            }
        }
    }

    fun buy(productId: String) {
        val catalog = _state.value.catalog ?: return
        val product = catalog.packages.find { it.id == productId } ?: return
        if (_state.value.purchasingId != null) return
        val userId = catalogRepository.currentUserId()
        if (!catalog.billingEnabled || userId.isNullOrBlank()) {
            _state.value = _state.value.copy(paymentMessage = "Платежи RuStore пока не настроены для этой сборки.")
            return
        }
        _state.value = _state.value.copy(purchasingId = productId, paymentMessage = null)
        purchaseLauncher.purchase(product.rustoreProductId, userId) { sdkResult ->
            sdkResult.fold(
                onSuccess = { proof ->
                    catalogRepository.savePendingRustore(proof.toPending(userId, product.id))
                    verify(product.id, proof)
                },
                onFailure = { error ->
                    val cancelled = error::class.simpleName?.contains("Cancelled") == true
                    _state.value = _state.value.copy(
                        purchasingId = null,
                        paymentMessage = if (cancelled) "Оплата отменена. Деньги не списаны." else "Не удалось открыть оплату RuStore. Попробуйте ещё раз.",
                        canRetryVerification = false,
                    )
                },
            )
        }
    }

    private fun verify(productId: String, proof: RuStorePurchaseProof) {
        viewModelScope.launch {
            try {
                val result = catalogRepository.verifyRustore(
                    productId = productId,
                    purchaseId = proof.purchaseId,
                    invoiceId = proof.invoiceId,
                    sandbox = proof.sandbox,
                )
                catalogRepository.clearPendingRustore(proof.purchaseId)
                purchaseLauncher.acknowledge(proof.purchaseId)
                _state.value = _state.value.copy(
                    purchasingId = null,
                    paymentMessage = if (result.granted) "Покупка подтверждена, баланс пополнен." else "Покупка уже была начислена ранее.",
                    canRetryVerification = false,
                )
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.value = _state.value.copy(
                    purchasingId = null,
                    paymentMessage = e.userMessage(),
                    canRetryVerification = true,
                )
            }
        }
    }

    fun retryVerification() {
        val pending = catalogRepository.pendingRustore() ?: return
        if (_state.value.purchasingId != null) return
        _state.value = _state.value.copy(purchasingId = pending.productId, paymentMessage = null, canRetryVerification = false)
        verify(pending.productId, pending.toProof())
    }

    private fun resumePending() {
        if (catalogRepository.pendingRustore() != null) retryVerification()
    }

    fun consumePaymentMessage() {
        _state.value = _state.value.copy(paymentMessage = null)
    }

    companion object {
        fun factory(catalogRepository: CatalogRepository, purchaseLauncher: PurchaseLauncher): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T {
                    return ShopViewModel(catalogRepository, purchaseLauncher) as T
                }
            }
    }
}

private fun RuStorePurchaseProof.toPending(userId: String, productId: String) = PendingRustorePurchase(
    userId = userId,
    productId = productId,
    purchaseId = purchaseId,
    invoiceId = invoiceId,
    sandbox = sandbox,
)

private fun PendingRustorePurchase.toProof() = RuStorePurchaseProof(purchaseId, invoiceId, sandbox)
