package ru.tarotsphere.app.ui.history

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import ru.tarotsphere.app.domain.model.HistoryItem
import ru.tarotsphere.app.domain.repository.UserRepository
import ru.tarotsphere.app.ui.components.*

data class HistoryUiState(
    val loading: Boolean = false, val items: List<HistoryItem> = emptyList(),
    val error: String? = null, val nextBeforeId: Long? = null,
)
class HistoryViewModel(private val repository: UserRepository) : ViewModel() {
    private val _state = MutableStateFlow(HistoryUiState())
    val state = _state.asStateFlow()
    init {
        viewModelScope.launch { repository.observeHistory().collect { _state.value = _state.value.copy(items = it) } }
    }
    fun refresh() = load(null)
    fun loadMore() { _state.value.nextBeforeId?.let { load(it) } }
    private fun load(beforeId: Long?) {
        if (_state.value.loading) return
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            try {
                val next = repository.refreshHistory(beforeId)
                _state.value = _state.value.copy(nextBeforeId = next)
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) { _state.value = _state.value.copy(error = e.userMessage())
            } finally { _state.value = _state.value.copy(loading = false) }
        }
    }
    companion object { fun factory(repository: UserRepository) = simpleFactory { HistoryViewModel(repository) } }
}
