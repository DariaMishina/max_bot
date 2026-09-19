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
import ru.tarotsphere.app.domain.repository.CatalogRepository

data class ShopUiState(
    val loading: Boolean = true,
    val catalog: Catalog? = null,
    val error: String? = null,
)

class ShopViewModel(
    private val catalogRepository: CatalogRepository,
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
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) {
                _state.value = ShopUiState(loading = false, error = e.userMessage())
            }
        }
    }

    companion object {
        fun factory(catalogRepository: CatalogRepository): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T {
                    return ShopViewModel(catalogRepository) as T
                }
            }
    }
}
