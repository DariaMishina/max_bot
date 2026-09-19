package ru.tarotsphere.app.ui.reading

import androidx.lifecycle.*
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import ru.tarotsphere.app.domain.model.*
import ru.tarotsphere.app.domain.repository.ReadingRepository
import ru.tarotsphere.app.ui.components.userMessage
import java.util.UUID

data class ReadingUiState(
    val loading: Boolean = false, val reading: Reading? = null, val offline: Boolean = false,
    val error: String? = null, val question: String = "", val sending: Boolean = false,
    val followUpError: String? = null, val retryPending: Boolean = false,
)
class ReadingViewModel(private val id: Long, private val repository: ReadingRepository, private val saved: SavedStateHandle) : ViewModel() {
    private val _state = MutableStateFlow(ReadingUiState(question = saved["question"] ?: "", retryPending = saved["pending"] ?: false))
    val state = _state.asStateFlow()
    fun refresh() {
        if (_state.value.loading || _state.value.sending) return
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            try {
                val result = repository.detail(id)
                _state.value = _state.value.copy(reading = result.value, offline = result.fromCache)
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) { _state.value = _state.value.copy(error = e.userMessage())
            } finally { _state.value = _state.value.copy(loading = false) }
        }
    }
    fun question(value: String) {
        if (_state.value.sending || _state.value.retryPending) return
        saved["question"] = value.take(1000)
        _state.value = _state.value.copy(question = value.take(1000), followUpError = null)
    }
    fun send() {
        val current = _state.value
        val reading = current.reading ?: return
        if (current.sending || (reading.followUpsRemaining <= 0 && !current.retryPending)) return
        if (current.question.isBlank()) {
            _state.value = current.copy(followUpError = "Напишите уточняющий вопрос.")
            return
        }
        val request = saved.get<String>("request") ?: UUID.randomUUID().toString().also { saved["request"] = it }
        saved["pending"] = true
        _state.value = current.copy(sending = true, retryPending = true, followUpError = null)
        viewModelScope.launch {
            try {
                val result = repository.followUp(reading, current.question.trim(), request)
                saved.remove<String>("request"); saved["question"] = ""; saved["pending"] = false
                _state.value = _state.value.copy(reading = result, question = "", offline = false, retryPending = false)
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) {
                if (e is AppFailure && e.code == "follow_up_limit") {
                    saved["pending"] = false
                    saved.remove<String>("request")
                    _state.value = _state.value.copy(reading = reading.copy(followUpsRemaining = 0), retryPending = false)
                }
                _state.value = _state.value.copy(followUpError = e.userMessage())
            } finally { _state.value = _state.value.copy(sending = false) }
        }
    }
    companion object {
        fun factory(id: Long, repository: ReadingRepository) = viewModelFactory {
            initializer { ReadingViewModel(id, repository, createSavedStateHandle()) }
        }
    }
}
