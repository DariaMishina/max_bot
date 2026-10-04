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
import ru.tarotsphere.app.domain.validation.INVALID_QUESTION_MESSAGE
import ru.tarotsphere.app.domain.validation.isMeaningfulQuestion
import ru.tarotsphere.app.domain.validation.normalizeQuestion
import ru.tarotsphere.app.ui.components.userMessage
import java.util.UUID

data class SpreadUiState(
    val question: String = "", val mode: CardSelectionMode = CardSelectionMode.RANDOM,
    val deck: List<TarotCard> = emptyList(), val selectedIds: List<String> = emptyList(),
    val catalog: List<TarotCard> = emptyList(),
    val namedQueries: List<String> = List(3) { "" },
    val namedCardIds: List<String?> = List(3) { null },
    val loadingDeck: Boolean = false, val loadingCatalog: Boolean = false, val submitting: Boolean = false,
    val error: String? = null, val resultId: Long? = null, val needsShop: Boolean = false,
    val retryPending: Boolean = false,
)

class SpreadViewModel(private val repository: ReadingRepository, private val saved: SavedStateHandle) : ViewModel() {
    private val _state = MutableStateFlow(SpreadUiState(
        question = saved["question"] ?: "", mode = restoredMode(saved),
        deck = restoredDeck(saved),
        selectedIds = saved.get<ArrayList<String>>("selected")?.toList().orEmpty(),
        namedQueries = restoredNamedQueries(saved), namedCardIds = restoredNamedIds(saved),
        resultId = saved["result"], retryPending = saved["pending"] ?: false,
    ))
    val state = _state.asStateFlow()
    init {
        when (_state.value.mode) {
            CardSelectionMode.INTUITIVE -> if (_state.value.deck.isEmpty() && !_state.value.retryPending) loadDeck()
            CardSelectionMode.NAMED -> if (!_state.value.retryPending) loadCatalog()
            CardSelectionMode.RANDOM -> Unit
        }
    }

    fun question(value: String) {
        if (_state.value.submitting || _state.value.retryPending) return
        saved["question"] = value.take(1000)
        _state.value = _state.value.copy(question = value.take(1000), error = null)
    }
    fun mode(mode: CardSelectionMode) {
        if (_state.value.submitting || _state.value.retryPending) return
        saved["mode"] = mode.name
        saved.remove<Boolean>("manual")
        saved["selected"] = arrayListOf<String>()
        saved["namedQueries"] = ArrayList(List(3) { "" })
        saved["namedIds"] = ArrayList(List(3) { "" })
        _state.value = _state.value.copy(
            mode = mode, selectedIds = emptyList(), namedQueries = List(3) { "" },
            namedCardIds = List(3) { null }, error = null,
        )
        if (mode == CardSelectionMode.INTUITIVE && _state.value.deck.isEmpty()) loadDeck()
        if (mode == CardSelectionMode.NAMED && _state.value.catalog.isEmpty()) loadCatalog()
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
    fun loadCatalog() {
        if (_state.value.loadingCatalog) return
        _state.value = _state.value.copy(loadingCatalog = true, error = null)
        viewModelScope.launch {
            try {
                _state.value = _state.value.copy(catalog = repository.deck(all = true))
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) { _state.value = _state.value.copy(error = e.userMessage())
            } finally { _state.value = _state.value.copy(loadingCatalog = false) }
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
    fun namedQuery(position: Int, value: String) {
        val current = _state.value
        if (current.submitting || current.retryPending || position !in 0..2) return
        val queries = current.namedQueries.toMutableList().also { it[position] = value }
        val exact = current.catalog.singleOrNull { normalizeCardName(it.name) == normalizeCardName(value) }
        val ids = current.namedCardIds.toMutableList().also {
            it[position] = exact?.id?.takeUnless { id -> current.namedCardIds.withIndex().any { entry -> entry.index != position && entry.value == id } }
        }
        saved["namedQueries"] = ArrayList(queries)
        saved["namedIds"] = ArrayList(ids.map { it.orEmpty() })
        _state.value = current.copy(namedQueries = queries, namedCardIds = ids, error = null)
    }
    fun selectNamed(position: Int, card: TarotCard) {
        val current = _state.value
        if (current.submitting || current.retryPending || position !in 0..2 ||
            current.namedCardIds.withIndex().any { it.index != position && it.value == card.id }) return
        val queries = current.namedQueries.toMutableList().also { it[position] = card.name }
        val ids = current.namedCardIds.toMutableList().also { it[position] = card.id }
        saved["namedQueries"] = ArrayList(queries)
        saved["namedIds"] = ArrayList(ids.map { it.orEmpty() })
        _state.value = current.copy(namedQueries = queries, namedCardIds = ids, error = null)
    }
    fun submit() {
        val current = _state.value
        if (current.submitting) return
        val cardIds = when (current.mode) {
            CardSelectionMode.RANDOM -> null
            CardSelectionMode.INTUITIVE -> current.selectedIds.takeIf { it.size == 3 }
            CardSelectionMode.NAMED -> current.namedCardIds.takeIf { ids -> ids.all { it != null } && ids.distinct().size == 3 }?.filterNotNull()
        }
        if (!isMeaningfulQuestion(current.question) || (current.mode != CardSelectionMode.RANDOM && cardIds == null)) {
            val error = when {
                !isMeaningfulQuestion(current.question) -> INVALID_QUESTION_MESSAGE
                current.mode == CardSelectionMode.NAMED -> "Укажите три разные карты из подсказок."
                else -> "Выберите 3 карты."
            }
            _state.value = current.copy(error = error)
            return
        }
        val requestId = saved.get<String>("request") ?: UUID.randomUUID().toString().also { saved["request"] = it }
        saved["pending"] = true
        _state.value = current.copy(submitting = true, retryPending = true, error = null)
        viewModelScope.launch {
            try {
                val reading = repository.create(normalizeQuestion(current.question), current.mode, cardIds, requestId)
                saved["result"] = reading.id
                saved["pending"] = false
                _state.value = _state.value.copy(resultId = reading.id, retryPending = false)
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) {
                val noBalance = (e as? AppFailure)?.code == "no_balance"
                _state.value = _state.value.copy(error = e.userMessage(), needsShop = noBalance)
                if (noBalance || (e is AppFailure && e.code in listOf("empty_question", "invalid_question", "invalid_cards", "long_question"))) {
                    saved["pending"] = false
                    saved.remove<String>("request")
                    _state.value = _state.value.copy(retryPending = false)
                }
            } finally { _state.value = _state.value.copy(submitting = false) }
        }
    }
    fun consumeResult() {
        listOf("question", "manual", "mode", "selected", "namedQueries", "namedIds", "result", "request", "pending", "deckIds", "deckNames", "deckImages").forEach { saved.remove<Any>(it) }
        _state.value = SpreadUiState()
    }
    fun consumeShop() { _state.value = _state.value.copy(needsShop = false) }
    companion object {
        fun factory(repository: ReadingRepository) = viewModelFactory {
            initializer { SpreadViewModel(repository, createSavedStateHandle()) }
        }
    }
}

private fun restoredMode(saved: SavedStateHandle): CardSelectionMode {
    val mode = saved.get<String>("mode")?.let { value -> CardSelectionMode.entries.firstOrNull { it.name == value } }
    return mode ?: if (saved.get<Boolean>("manual") == true) CardSelectionMode.INTUITIVE else CardSelectionMode.RANDOM
}

private fun restoredNamedQueries(saved: SavedStateHandle): List<String> =
    saved.get<ArrayList<String>>("namedQueries")?.takeIf { it.size == 3 }?.toList() ?: List(3) { "" }

private fun restoredNamedIds(saved: SavedStateHandle): List<String?> =
    saved.get<ArrayList<String>>("namedIds")?.takeIf { it.size == 3 }?.map { it.ifBlank { null } } ?: List(3) { null }

private fun normalizeCardName(value: String) = value.trim().lowercase().replace('ё', 'е')

private fun restoredDeck(saved: SavedStateHandle): List<TarotCard> {
    val ids = saved.get<ArrayList<String>>("deckIds") ?: return emptyList()
    val names = saved.get<ArrayList<String>>("deckNames") ?: return emptyList()
    val images = saved.get<ArrayList<String>>("deckImages") ?: return emptyList()
    if (ids.size != names.size || ids.size != images.size) return emptyList()
    return ids.indices.map { TarotCard(ids[it], names[it], images[it]) }
}
