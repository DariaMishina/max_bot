package ru.tarotsphere.app.ui.spread

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.tarotsphere.app.domain.model.TarotCard
import ru.tarotsphere.app.ui.components.*
import ru.tarotsphere.app.ui.theme.TarotSphereTheme

@Composable
fun SpreadScreen(viewModel: SpreadViewModel, onResult: (Long) -> Unit, onShop: () -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val focus = LocalFocusManager.current
    LaunchedEffect(state.resultId) {
        state.resultId?.let { onResult(it); viewModel.consumeResult() }
    }
    LaunchedEffect(state.needsShop) {
        if (state.needsShop) { onShop(); viewModel.consumeShop() }
    }
    SpreadContent(
        state = state, onQuestion = viewModel::question,
        onMode = { manual -> focus.clearFocus(); if (manual != state.manual) viewModel.mode(manual) },
        onSelect = { id -> focus.clearFocus(); viewModel.select(id) }, onLoadDeck = viewModel::loadDeck,
        onSubmit = { focus.clearFocus(); viewModel.submit() },
    )
}

@Composable
private fun SpreadContent(
    state: SpreadUiState, onQuestion: (String) -> Unit, onMode: (Boolean) -> Unit,
    onSelect: (String) -> Unit, onLoadDeck: () -> Unit, onSubmit: () -> Unit,
) {
    val colors = MaterialTheme.colorScheme
    val editable = !state.submitting && !state.retryPending
    SphereScreen {
        SphereHeader("О чём спросим карты?", "Можно начать с того, что сейчас занимает ваши мысли.", "Сфера Таро")
        QuestionField(state.question, onQuestion, label = "Ваш вопрос", enabled = editable,
            placeholder = "На что обратить внимание в отношениях?")
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Как выберем карты", style = MaterialTheme.typography.titleLarge)
            Column(Modifier.selectableGroup(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                ChoiceOption("Карты сами", "Три случайные карты для вашего вопроса", !state.manual, { onMode(false) }, editable)
                ChoiceOption("Выбрать самой", "Откройте три карты из девяти", state.manual, { onMode(true) }, editable)
            }
        }
        if (state.manual) {
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
        state.error?.let { StatusPanel("Не удалось получить ответ", it, StatusTone.Error) }
        when {
            state.submitting -> StatusPanel("Готовим толкование", "Это может занять до полутора минут. Готовый расклад сохранится в истории.", StatusTone.Progress)
            state.retryPending -> StatusPanel("Ответ ещё не получен", "Повторите этот запрос или проверьте историю. Повтор не расходует дополнительный расклад.")
        }
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            PrimaryAction(
                text = if (state.retryPending && !state.submitting) "Повторить запрос" else if (state.submitting) "Готовим толкование…" else "Получить толкование",
                onClick = onSubmit,
                enabled = !state.submitting && state.question.isNotBlank() && (!state.manual || state.selectedIds.size == 3),
            )
            Text("Расклад — повод для размышления. Решения остаются за вами.", color = colors.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Preview(widthDp = 360, heightDp = 800, showBackground = true)
@Preview(name = "Крупный шрифт", widthDp = 360, heightDp = 800, fontScale = 2f, showBackground = true)
@Composable
private fun SpreadPreview() {
    TarotSphereTheme { SpreadContent(SpreadUiState(), {}, {}, {}, {}, {}) }
}

@Preview(name = "Выбор карт", widthDp = 412, heightDp = 1000, showBackground = true)
@Composable
private fun ManualSpreadPreview() {
    TarotSphereTheme { SpreadContent(SpreadUiState(question = "Что поможет мне двигаться вперёд?", manual = true,
        deck = (1..9).map { TarotCard(it.toString(), "Карта $it", "") }), {}, {}, {}, {}, {}) }
}
