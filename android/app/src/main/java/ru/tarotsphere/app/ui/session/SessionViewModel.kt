package ru.tarotsphere.app.ui.session

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import ru.tarotsphere.app.domain.session.OnboardingStore
import ru.tarotsphere.app.domain.usecase.EnsureGuestSessionUseCase

data class SessionUiState(
    val loading: Boolean = true,
    val needsOnboarding: Boolean = false,
    val ready: Boolean = false,
    val error: String? = null,
)

class SessionViewModel(
    private val ensureGuestSession: EnsureGuestSessionUseCase,
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
            connectGuest()
        }
    }

    fun completeOnboarding() {
        onboardingStore.markCompleted()
        viewModelScope.launch { connectGuest() }
    }

    fun retry() {
        viewModelScope.launch { connectGuest() }
    }

    private suspend fun connectGuest() {
        _state.value = SessionUiState(loading = true)
        try {
            ensureGuestSession()
            _state.value = SessionUiState(loading = false, ready = true)
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
            onboardingStore: OnboardingStore,
        ): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return SessionViewModel(ensureGuestSession, onboardingStore) as T
            }
        }
    }
}
