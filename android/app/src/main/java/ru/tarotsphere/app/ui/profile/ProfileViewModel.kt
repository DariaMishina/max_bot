package ru.tarotsphere.app.ui.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import ru.tarotsphere.app.domain.model.UserProfile
import ru.tarotsphere.app.domain.repository.UserRepository
import ru.tarotsphere.app.ui.components.*

data class ProfileUiState(
    val loading: Boolean = false, val profile: UserProfile? = null, val offline: Boolean = false,
    val error: String? = null, val feedback: String = "", val sending: Boolean = false,
    val feedbackMessage: String? = null, val deleting: Boolean = false, val deleted: Boolean = false,
    val deleteError: String? = null,
)
class ProfileViewModel(private val repository: UserRepository) : ViewModel() {
    private val _state = MutableStateFlow(ProfileUiState())
    val state = _state.asStateFlow()
    fun refresh() {
        if (_state.value.loading || _state.value.deleting) return
        _state.value = _state.value.copy(loading = true, error = null)
        viewModelScope.launch {
            try {
                val result = repository.me()
                _state.value = _state.value.copy(profile = result.value, offline = result.fromCache)
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) { _state.value = _state.value.copy(error = e.userMessage())
            } finally { _state.value = _state.value.copy(loading = false) }
        }
    }
    fun feedback(value: String) {
        if (!_state.value.sending) _state.value = _state.value.copy(feedback = value.take(2000), feedbackMessage = null)
    }
    fun sendFeedback() {
        val current = _state.value
        if (current.sending || current.deleting || current.feedback.isBlank()) return
        _state.value = current.copy(sending = true, feedbackMessage = null)
        viewModelScope.launch {
            try {
                repository.feedback(current.feedback.trim())
                _state.value = _state.value.copy(feedback = "", feedbackMessage = "Спасибо! Ваше сообщение сохранено для поддержки.")
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) { _state.value = _state.value.copy(feedbackMessage = e.userMessage())
            } finally { _state.value = _state.value.copy(sending = false) }
        }
    }
    fun deleteData() {
        if (_state.value.deleting || _state.value.sending || _state.value.loading) return
        _state.value = _state.value.copy(deleting = true, deleteError = null)
        viewModelScope.launch {
            try {
                repository.deleteData()
                _state.value = ProfileUiState(deleted = true)
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) { _state.value = _state.value.copy(deleting = false, deleteError = e.userMessage()) }
        }
    }
    companion object { fun factory(repository: UserRepository) = simpleFactory { ProfileViewModel(repository) } }
}
