package ru.tarotsphere.app.ui.spread

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import ru.tarotsphere.app.domain.model.*
import ru.tarotsphere.app.domain.repository.*
import ru.tarotsphere.app.ui.components.userMessage
import java.util.UUID

data class SpreadUiState(
    val question: String = "", val manual: Boolean = false,
    val deck: List<TarotCard> = emptyList(), val selectedIds: List<String> = emptyList(),
    val loadingDeck: Boolean = false, val submitting: Boolean = false,
    val error: String? = null, val resultId: Long? = null, val needsShop: Boolean = false,
    val retryPending: Boolean = false,
)

class SpreadViewModel(private val repository: ReadingRepository, private val saved: SavedStateHandle) : ViewModel() {
    private val _state = MutableStateFlow(SpreadUiState(
        question = saved["question"] ?: "", manual = saved["manual"] ?: false,
        deck = restoredDeck(saved),
        selectedIds = saved.get<ArrayList<String>>("selected")?.toList().orEmpty(),
        resultId = saved["result"], retryPending = saved["pending"] ?: false,
    ))
    val state = _state.asStateFlow()
    init { if (_state.value.manual && _state.value.deck.isEmpty() && !_state.value.retryPending) loadDeck() }

    fun question(value: String) {
        if (_state.value.submitting || _state.value.retryPending) return
        saved["question"] = value.take(1000)
        _state.value = _state.value.copy(question = value.take(1000), error = null)
    }
    fun mode(manual: Boolean) {
        if (_state.value.submitting || _state.value.retryPending) return
        saved["manual"] = manual
        saved["selected"] = arrayListOf<String>()
        _state.value = _state.value.copy(manual = manual, selectedIds = emptyList(), error = null)
        if (manual && _state.value.deck.isEmpty()) loadDeck()
    }
    fun loadDeck() {
        if (_state.value.loadingDeck) return
        _state.value = _state.value.copy(loadingDeck = true, error = null)
        viewModelScope.launch {
            try {
                val deck = repository.deck()
                saved["deckIds"] = ArrayList(deck.map { it.id })
                saved["deckNames"] = ArrayList(deck.map { it.name })
                saved["deckImages"] = ArrayList(deck.map { it.imageUrl })
                // A pending request keeps its original 3 IDs even after process death.
                val selected = if (_state.value.retryPending) _state.value.selectedIds else emptyList()
                _state.value = _state.value.copy(deck = deck, selectedIds = selected)
                saved["selected"] = ArrayList(selected)
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) { _state.value = _state.value.copy(error = e.userMessage())
            } finally { _state.value = _state.value.copy(loadingDeck = false) }
        }
    }
    fun select(id: String) {
        val current = _state.value
        if (current.submitting || current.retryPending || current.deck.none { it.id == id }) return
        val selected = when {
            id in current.selectedIds -> current.selectedIds - id
            current.selectedIds.size < 3 -> current.selectedIds + id
            else -> current.selectedIds
        }
        saved["selected"] = ArrayList(selected)
        _state.value = current.copy(selectedIds = selected, error = null)
    }
    fun submit() {
        val current = _state.value
        if (current.submitting) return
        if (current.question.isBlank() || (current.manual && current.selectedIds.size != 3)) {
            _state.value = current.copy(error = if (current.question.isBlank()) "Напишите свой вопрос." else "Выберите 3 карты.")
            return
        }
        val requestId = saved.get<String>("request") ?: UUID.randomUUID().toString().also { saved["request"] = it }
        saved["pending"] = true
        _state.value = current.copy(submitting = true, retryPending = true, error = null)
        viewModelScope.launch {
            try {
                val reading = repository.create(current.question.trim(), current.selectedIds.takeIf { current.manual }, requestId)
                saved["result"] = reading.id
                saved["pending"] = false
                _state.value = _state.value.copy(resultId = reading.id, retryPending = false)
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) {
                val noBalance = (e as? AppFailure)?.code == "no_balance"
                _state.value = _state.value.copy(error = e.userMessage(), needsShop = noBalance)
                if (noBalance || (e is AppFailure && e.code in listOf("empty_question", "invalid_cards", "long_question"))) {
                    saved["pending"] = false
                    saved.remove<String>("request")
                    _state.value = _state.value.copy(retryPending = false)
                }
            } finally { _state.value = _state.value.copy(submitting = false) }
        }
    }
    fun consumeResult() {
        listOf("question", "manual", "selected", "result", "request", "pending", "deckIds", "deckNames", "deckImages").forEach { saved.remove<Any>(it) }
        _state.value = SpreadUiState()
    }
    fun consumeShop() { _state.value = _state.value.copy(needsShop = false) }
    companion object {
        fun factory(repository: ReadingRepository) = viewModelFactory {
            initializer { SpreadViewModel(repository, createSavedStateHandle()) }
        }
    }
}

private fun restoredDeck(saved: SavedStateHandle): List<TarotCard> {
    val ids = saved.get<ArrayList<String>>("deckIds") ?: return emptyList()
    val names = saved.get<ArrayList<String>>("deckNames") ?: return emptyList()
    val images = saved.get<ArrayList<String>>("deckImages") ?: return emptyList()
    if (ids.size != names.size || ids.size != images.size) return emptyList()
    return ids.indices.map { TarotCard(ids[it], names[it], images[it]) }
}
