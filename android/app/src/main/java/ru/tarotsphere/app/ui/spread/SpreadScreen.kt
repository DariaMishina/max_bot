@file:OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)

package ru.tarotsphere.app.ui.spread

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import ru.tarotsphere.app.domain.model.CardSelectionMode
import ru.tarotsphere.app.domain.model.TarotCard
import ru.tarotsphere.app.domain.validation.isMeaningfulQuestion
import ru.tarotsphere.app.ui.components.*
import ru.tarotsphere.app.ui.theme.TarotSphereTheme

@Composable
fun SpreadScreen(viewModel: SpreadViewModel, onResult: (Long) -> Unit, onShop: () -> Unit, onAccount: () -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val focus = LocalFocusManager.current
    LaunchedEffect(state.resultId) {
        state.resultId?.let { onResult(it); viewModel.consumeResult() }
    }
    val lifecycleOwner = androidx.lifecycle.compose.LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = androidx.lifecycle.LifecycleEventObserver { _, event ->
            if (event == androidx.lifecycle.Lifecycle.Event.ON_RESUME) viewModel.refreshBalance()
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }
    LaunchedEffect(Unit) { viewModel.refreshBalance() }
    SpreadContent(
        state = state, onQuestion = viewModel::question,
        onMode = { mode -> focus.clearFocus(); if (mode != state.mode) viewModel.mode(mode) },
        onSelect = { id -> focus.clearFocus(); viewModel.select(id) }, onLoadDeck = viewModel::loadDeck,
        onNamedQuery = viewModel::namedQuery,
        onNamedSelect = { position, card -> focus.clearFocus(); viewModel.selectNamed(position, card) },
        onLoadCatalog = viewModel::loadCatalog,
        onSubmit = { focus.clearFocus(); viewModel.submit() },
        onShop = onShop, onAccount = onAccount, onRefresh = viewModel::refreshBalance,
    )
}

@Composable
private fun SpreadContent(
    state: SpreadUiState, onQuestion: (String) -> Unit, onMode: (CardSelectionMode) -> Unit,
    onSelect: (String) -> Unit, onLoadDeck: () -> Unit,
    onNamedQuery: (Int, String) -> Unit, onNamedSelect: (Int, TarotCard) -> Unit,
    onLoadCatalog: () -> Unit, onSubmit: () -> Unit,
    onShop: () -> Unit = {}, onAccount: () -> Unit = {}, onRefresh: () -> Unit = {},
) {
    val colors = MaterialTheme.colorScheme
    val editable = !state.submitting && !state.retryPending
    val focus = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current
    val scope = rememberCoroutineScope()
    val modeRequester = remember { BringIntoViewRequester() }
    val actionRequester = remember { BringIntoViewRequester() }
    val readyForAction = isMeaningfulQuestion(state.question) && when (state.mode) {
        CardSelectionMode.RANDOM -> true
        CardSelectionMode.INTUITIVE -> state.selectedIds.size == 3
        CardSelectionMode.NAMED -> state.namedCardIds.all { it != null } && state.namedCardIds.distinct().size == 3
    }
    LaunchedEffect(readyForAction, state.mode, state.submitting, state.retryPending) {
        if (readyForAction && state.mode != CardSelectionMode.RANDOM && !state.submitting && !state.retryPending) {
            delay(120)
            actionRequester.bringIntoView()
        }
    }
    SphereScreen {
        if (!state.retryPending && !state.submitting) {
            if (state.loadingBalance) {
                SphereHeader("Проверяем доступные расклады", "Это займёт несколько секунд.")
                LinearProgressIndicator(Modifier.fillMaxWidth())
                return@SphereScreen
            }
            if (state.balanceError != null) {
                StatusPanel("Не удалось проверить баланс", state.balanceError, StatusTone.Error)
                PrimaryAction("Повторить проверку", onRefresh)
                return@SphereScreen
            }
            if (state.needsShop || state.balance?.canDivinate == false) {
                val message = emptyBalanceMessage(state.balance)
                SphereHeader(message.first, message.second, "Сфера Таро")
                if (state.question.isNotBlank()) {
                    Text("Ваш вопрос и выбранные карты сохранены. После покупки вернитесь во вкладку «Расклад».",
                        color = colors.onSurfaceVariant)
                }
                PrimaryAction("Выбрать пакет", onShop)
                SecondaryAction("Открыть профиль и сменить аккаунт", onAccount)
                Text("Если расклады остались в другом аккаунте, войдите в него через профиль.",
                    style = MaterialTheme.typography.bodySmall, color = colors.onSurfaceVariant)
                SecondaryAction("Обновить баланс", onRefresh)
                return@SphereScreen
            }
        }
        SphereHeader("О чём спросим карты?", "Можно начать с того, что сейчас занимает ваши мысли.", "Сфера Таро")
        QuestionField(
            state.question, onQuestion, label = "Ваш вопрос", enabled = editable, minLines = 2, maxLines = 5,
            placeholder = "На что обратить внимание в отношениях?",
            onImeDone = {
                focus.clearFocus()
                keyboard?.hide()
                scope.launch { delay(120); modeRequester.bringIntoView() }
            },
        )
        if (state.question.isNotBlank() && !isMeaningfulQuestion(state.question)) {
            Text(
                "Напишите вопрос или тему словами.",
                style = MaterialTheme.typography.bodySmall,
                color = colors.error,
            )
        }
        Column(Modifier.bringIntoViewRequester(modeRequester), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Как откроем карты?", style = MaterialTheme.typography.titleLarge)
            Column(Modifier.selectableGroup(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                ChoiceOption("Довериться колоде", "Три случайные карты для вашего вопроса", state.mode == CardSelectionMode.RANDOM, { onMode(CardSelectionMode.RANDOM) }, editable)
                ChoiceOption("Выбрать интуитивно", "Откройте три из девяти закрытых карт", state.mode == CardSelectionMode.INTUITIVE, { onMode(CardSelectionMode.INTUITIVE) }, editable)
                ChoiceOption("Указать свои карты", "Выберите названия карт вашей колоды", state.mode == CardSelectionMode.NAMED, { onMode(CardSelectionMode.NAMED) }, editable)
            }
        }
        if (state.mode == CardSelectionMode.INTUITIVE) {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                SphereHeader("Выбрано ${state.selectedIds.size} из 3", when (state.selectedIds.size) {
                    0 -> "Первая карта — прошлое. Нажмите на любую рубашку."
                    1 -> "Вторая карта — настоящее."
                    2 -> "Третья карта — будущее."
                    else -> "Карты выбраны. Повторное нажатие отменяет выбор."
                })
                if (state.loadingDeck) LinearProgressIndicator(Modifier.fillMaxWidth(), color = colors.secondary)
                state.deck.chunked(3).forEach { row ->
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        row.forEach { card ->
                            val position = state.selectedIds.indexOf(card.id).takeIf { it >= 0 }?.plus(1)
                            TarotCardView(card, revealed = position != null, selection = position, modifier = Modifier.weight(1f),
                                enabled = editable && (position != null || state.selectedIds.size < 3), onClick = { onSelect(card.id) })
                        }
                    }
                }
                if (state.deck.isEmpty() && !state.loadingDeck) SecondaryAction("Загрузить карты", onLoadDeck, enabled = editable)
            }
        }
        if (state.mode == CardSelectionMode.NAMED) {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                SphereHeader("Карты вашего расклада", "Начните вводить название и выберите карту из подсказок.")
                if (state.loadingCatalog) LinearProgressIndicator(Modifier.fillMaxWidth(), color = colors.secondary)
                listOf("Прошлое", "Настоящее", "Будущее").forEachIndexed { index, position ->
                    NamedCardField(
                        position = position, query = state.namedQueries[index], selectedId = state.namedCardIds[index],
                        catalog = state.catalog, unavailableIds = state.namedCardIds.filterNotNull().toSet() - setOfNotNull(state.namedCardIds[index]),
                        enabled = editable, onQuery = { onNamedQuery(index, it) }, onSelect = { onNamedSelect(index, it) },
                    )
                }
                if (state.catalog.isEmpty() && !state.loadingCatalog) SecondaryAction("Загрузить названия карт", onLoadCatalog, enabled = editable)
            }
        }
        state.error?.let { StatusPanel("Не удалось получить ответ", it, StatusTone.Error) }
        when {
            state.submitting -> StatusPanel("Готовим толкование", "Это может занять до полутора минут. Готовый расклад сохранится в истории.", StatusTone.Progress)
            state.retryPending -> StatusPanel("Ответ ещё не получен", "Повторите этот запрос или проверьте историю. Повтор не расходует дополнительный расклад.")
        }
        Column(Modifier.bringIntoViewRequester(actionRequester), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            PrimaryAction(
                text = if (state.retryPending && !state.submitting) "Повторить запрос" else if (state.submitting) "Готовим толкование…" else "Получить толкование",
                onClick = onSubmit,
                enabled = !state.submitting && readyForAction,
            )
            Text("Карты подскажут направление, но выбор всегда остаётся за вами.", color = colors.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun NamedCardField(
    position: String, query: String, selectedId: String?, catalog: List<TarotCard>, unavailableIds: Set<String>,
    enabled: Boolean, onQuery: (String) -> Unit, onSelect: (TarotCard) -> Unit,
) {
    var focused by remember { mutableStateOf(false) }
    val suggestions = remember(query, catalog, unavailableIds) {
        val needle = query.trim().lowercase().replace('ё', 'е')
        catalog.asSequence()
            .filter { it.id !in unavailableIds && (needle.isEmpty() || it.name.lowercase().replace('ё', 'е').contains(needle)) }
            .take(6).toList()
    }
    Box {
        OutlinedTextField(
            value = query, onValueChange = onQuery, enabled = enabled, singleLine = true,
            label = { Text(position) }, placeholder = { Text("Начните вводить название") },
            supportingText = { if (selectedId != null) Text("Карта выбрана") else Text("Выберите карту из подсказок") },
            modifier = Modifier.fillMaxWidth().onFocusChanged { focused = it.isFocused },
            shape = MaterialTheme.shapes.medium,
        )
        DropdownMenu(expanded = focused && enabled && suggestions.isNotEmpty(), onDismissRequest = { focused = false }) {
            suggestions.forEach { card ->
                DropdownMenuItem(text = { Text(card.name) }, onClick = { focused = false; onSelect(card) })
            }
        }
    }
}

@Preview(widthDp = 360, heightDp = 800, showBackground = true)
@Preview(name = "Крупный шрифт", widthDp = 360, heightDp = 800, fontScale = 2f, showBackground = true)
@Composable
private fun SpreadPreview() {
    TarotSphereTheme { SpreadContent(SpreadUiState(), {}, {}, {}, {}, { _, _ -> }, { _, _ -> }, {}, {}) }
}

@Preview(name = "Выбор карт", widthDp = 412, heightDp = 1000, showBackground = true)
@Composable
private fun ManualSpreadPreview() {
    TarotSphereTheme { SpreadContent(SpreadUiState(question = "Что поможет мне двигаться вперёд?", mode = CardSelectionMode.INTUITIVE,
        deck = (1..9).map { TarotCard(it.toString(), "Карта $it", "") }), {}, {}, {}, {}, { _, _ -> }, { _, _ -> }, {}, {}) }
}

internal fun emptyBalanceMessage(balance: ru.tarotsphere.app.domain.model.Balance?): Pair<String, String> = when {
    balance != null && balance.totalUsed > 0 -> "Ваши расклады закончились" to
        "Выберите пакет, чтобы продолжить. Ваши предыдущие расклады доступны в истории."
    balance?.trialStatus == "device_used" -> "Приветственный подарок уже получен" to
        "На этом устройстве три бесплатных расклада уже были предоставлены. Создание нового аккаунта не добавляет бесплатные расклады."
    balance?.trialStatus == "daily_limit" -> "Приветственный подарок не начислен" to
        "Выдача новых подарков была временно ограничена при регистрации. В этом аккаунте пока нет доступных раскладов."
    else -> "Нет доступных раскладов" to
        "В этом аккаунте сейчас нет бесплатных или оплаченных раскладов. Чтобы продолжить, выберите пакет в магазине."
}
