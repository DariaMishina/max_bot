package ru.tarotsphere.app.ui.spread

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import ru.tarotsphere.app.domain.model.Balance
import ru.tarotsphere.app.domain.repository.UserRepository

data class SpreadUiState(
    val loading: Boolean = true,
    val balance: Balance? = null,
    val error: String? = null,
)

class SpreadViewModel(
    private val userRepository: UserRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(SpreadUiState())
    val state: StateFlow<SpreadUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun refresh() {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)
            try {
                _state.value = SpreadUiState(loading = false, balance = userRepository.balance())
            } catch (e: Exception) {
                _state.value = SpreadUiState(loading = false, error = e.message ?: "Ошибка загрузки")
            }
        }
    }

    companion object {
        fun factory(userRepository: UserRepository): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T {
                    return SpreadViewModel(userRepository) as T
                }
            }
    }
}
