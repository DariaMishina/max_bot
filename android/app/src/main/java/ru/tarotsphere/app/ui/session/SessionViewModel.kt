package ru.tarotsphere.app.ui.session

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import ru.tarotsphere.app.domain.repository.AuthRepository
import ru.tarotsphere.app.domain.session.OnboardingStore
import ru.tarotsphere.app.domain.usecase.EnsureGuestSessionUseCase
import ru.tarotsphere.app.ui.components.userMessage

data class SessionUiState(
    val loading: Boolean = true,
    val needsOnboarding: Boolean = false,
    val needsAuth: Boolean = false,
    val ready: Boolean = false,
    val email: String = "",
    val code: String = "",
    val codeSent: Boolean = false,
    val submitting: Boolean = false,
    val error: String? = null,
)

class SessionViewModel(
    private val ensureGuestSession: EnsureGuestSessionUseCase,
    private val authRepository: AuthRepository,
    private val onboardingStore: OnboardingStore,
) : ViewModel() {

    private val _state = MutableStateFlow(SessionUiState())
    val state: StateFlow<SessionUiState> = _state.asStateFlow()

    init {
        start()
    }

    fun start() {
        viewModelScope.launch {
            _state.value = SessionUiState(loading = true)
            if (!onboardingStore.isCompleted()) {
                _state.value = SessionUiState(loading = false, needsOnboarding = true)
                return@launch
            }
            restoreSession()
        }
    }

    fun completeOnboarding() {
        onboardingStore.markCompleted()
        _state.value = SessionUiState(loading = false, needsAuth = true)
    }

    fun retry() {
        viewModelScope.launch { restoreSession() }
    }

    fun email(value: String) {
        if (!_state.value.submitting && !_state.value.codeSent) {
            _state.value = _state.value.copy(email = value.take(320), error = null)
        }
    }

    fun code(value: String) {
        if (!_state.value.submitting) {
            _state.value = _state.value.copy(code = value.filter(Char::isDigit).take(6), error = null)
        }
    }

    fun requestEmailCode() {
        val email = _state.value.email.trim()
        if (_state.value.submitting || '@' !in email) {
            _state.value = _state.value.copy(error = "Проверьте адрес электронной почты")
            return
        }
        _state.value = _state.value.copy(submitting = true, error = null)
        viewModelScope.launch {
            try {
                authRepository.requestEmailCode(email)
                _state.value = _state.value.copy(codeSent = true)
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) { _state.value = _state.value.copy(error = e.userMessage())
            } finally { _state.value = _state.value.copy(submitting = false) }
        }
    }

    fun confirmEmail() {
        val current = _state.value
        if (current.submitting || current.code.length != 6) {
            _state.value = current.copy(error = "Введите шестизначный код")
            return
        }
        _state.value = current.copy(submitting = true, error = null)
        viewModelScope.launch {
            try {
                authRepository.confirmEmail(current.email, current.code)
                _state.value = SessionUiState(loading = false, ready = true)
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) { _state.value = _state.value.copy(error = e.userMessage())
            } finally {
                if (!_state.value.ready) _state.value = _state.value.copy(submitting = false)
            }
        }
    }

    fun changeEmail() {
        if (!_state.value.submitting) _state.value = _state.value.copy(code = "", codeSent = false, error = null)
    }

    private suspend fun restoreSession() {
        _state.value = SessionUiState(loading = true)
        try {
            val confirmed = ensureGuestSession()
            _state.value = SessionUiState(loading = false, ready = confirmed, needsAuth = !confirmed)
        } catch (e: Exception) {
            _state.value = SessionUiState(
                loading = false,
                error = e.message ?: "Не удалось связаться с сервером",
            )
        }
    }

    companion object {
        fun factory(
            ensureGuestSession: EnsureGuestSessionUseCase,
            authRepository: AuthRepository,
            onboardingStore: OnboardingStore,
        ): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return SessionViewModel(ensureGuestSession, authRepository, onboardingStore) as T
            }
        }
    }
}
