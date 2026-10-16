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
    val passwordMode: Boolean = true,
    val registering: Boolean = false,
    val login: String = "",
    val password: String = "",
    val passwordConfirmation: String = "",
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

    suspend fun recoveryStart(login: String, email: String, password: String) =
        authRepository.recoveryStart(false, login, email, password)
    suspend fun recoveryConfirm(challenge: String, code: String, password: String) =
        authRepository.recoveryConfirm(false, challenge, code, password)

    fun email(value: String) {
        if (!_state.value.submitting && !_state.value.codeSent) {
            _state.value = _state.value.copy(email = value.take(320), error = null)
        }
    }

    fun passwordMode(enabled: Boolean) {
        if (!_state.value.submitting) _state.value = _state.value.copy(
            passwordMode = enabled, password = "", passwordConfirmation = "", code = "", codeSent = false, error = null,
        )
    }

    fun registering(enabled: Boolean) {
        if (!_state.value.submitting) _state.value = _state.value.copy(
            registering = enabled, password = "", passwordConfirmation = "", error = null,
        )
    }

    fun login(value: String) {
        if (!_state.value.submitting) _state.value = _state.value.copy(login = value.take(32), error = null)
    }

    fun password(value: String) {
        if (!_state.value.submitting) _state.value = _state.value.copy(password = value.take(128), error = null)
    }

    fun passwordConfirmation(value: String) {
        if (!_state.value.submitting) _state.value = _state.value.copy(passwordConfirmation = value.take(128), error = null)
    }

    fun authenticatePassword() {
        val current = _state.value
        if (current.submitting) return
        val error = when {
            !current.login.trim().matches(Regex("[a-zA-Z0-9_]{6,32}")) -> "Логин: 6–32 латинские буквы, цифры или _"
            current.password.length !in 12..128 -> "Пароль должен содержать от 12 до 128 символов"
            current.registering && current.password != current.passwordConfirmation -> "Пароли не совпадают"
            else -> null
        }
        if (error != null) {
            _state.value = current.copy(error = error)
            return
        }
        _state.value = current.copy(submitting = true, error = null)
        viewModelScope.launch {
            try {
                authRepository.authenticatePassword(current.login, current.password, current.registering)
                _state.value = SessionUiState(loading = false, ready = true)
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) { _state.value = _state.value.copy(error = e.userMessage())
            } finally {
                if (!_state.value.ready) _state.value = _state.value.copy(submitting = false, password = "", passwordConfirmation = "")
            }
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

    fun beginVkAuth() {
        if (!_state.value.submitting) {
            _state.value = _state.value.copy(submitting = true, error = null)
        }
    }

    fun confirmVk(accessToken: String) {
        viewModelScope.launch {
            try {
                authRepository.confirmVk(accessToken)
                _state.value = SessionUiState(loading = false, ready = true)
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) { _state.value = _state.value.copy(error = e.userMessage())
            } finally {
                if (!_state.value.ready) _state.value = _state.value.copy(submitting = false)
            }
        }
    }

    fun failVk(message: String?) {
        _state.value = _state.value.copy(submitting = false, error = message)
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
