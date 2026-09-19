package ru.tarotsphere.app.ui.spread

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.tarotsphere.app.ui.components.*
import ru.tarotsphere.app.ui.theme.*

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
    Column(
        Modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Ваш расклад", style = MaterialTheme.typography.headlineMedium)
        Text("Остановитесь на минуту. О чём вы хотите спросить карты?", color = CreamMuted)
        DeckCard {
            Text("1 · Сформулируйте вопрос", style = MaterialTheme.typography.titleMedium, color = Gold)
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = state.question, onValueChange = viewModel::question,
                label = { Text("Ваш вопрос") }, placeholder = { Text("На что обратить внимание в отношениях?") },
                supportingText = { Text("${state.question.length}/1000") },
                modifier = Modifier.fillMaxWidth(), minLines = 3, maxLines = 6,
                enabled = !state.submitting && !state.retryPending,
            )
        }
        DeckCard {
            Text("2 · Выберите способ", style = MaterialTheme.typography.titleMedium, color = Gold)
            Spacer(Modifier.height(8.dp))
            Column {
                FilterChip(modifier = Modifier.fillMaxWidth(), selected = !state.manual, onClick = { viewModel.mode(false) }, label = { Text("Карты сами") }, enabled = !state.submitting && !state.retryPending)
                FilterChip(modifier = Modifier.fillMaxWidth(), selected = state.manual, onClick = { viewModel.mode(true) }, label = { Text("Выбрать самой") }, enabled = !state.submitting && !state.retryPending)
            }
            Text(if (state.manual) "Выберите 3 карты из 9. Повторное нажатие отменяет выбор." else "Для вашего вопроса случайно выпадут три карты.", color = CreamMuted, style = MaterialTheme.typography.bodyMedium)
        }
        if (state.manual) {
            Text("Выбрано ${state.selectedIds.size} из 3", style = MaterialTheme.typography.titleMedium)
            Text("1 — прошлое · 2 — настоящее · 3 — будущее", style = MaterialTheme.typography.bodySmall, color = CreamMuted)
            if (state.loadingDeck) CircularProgressIndicator(color = Gold)
            state.deck.chunked(3).forEach { row ->
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    row.forEach { card ->
                        val position = state.selectedIds.indexOf(card.id).takeIf { it >= 0 }?.plus(1)
                        TarotCardView(card, revealed = position != null, selection = position, modifier = Modifier.weight(1f),
                            enabled = !state.submitting && !state.retryPending && (position != null || state.selectedIds.size < 3), onClick = { viewModel.select(card.id) })
                    }
                }
            }
            if (state.deck.isEmpty() && !state.loadingDeck) TextButton(onClick = viewModel::loadDeck) { Text("Загрузить карты") }
        }
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        if (state.submitting) {
            DeckCard {
                CircularProgressIndicator(color = Gold)
                Spacer(Modifier.height(12.dp))
                Text("Готовим толкование…", style = MaterialTheme.typography.titleMedium)
                Text("Обычно это занимает до полутора минут. Готовый расклад появится в истории.", color = CreamMuted)
            }
        } else if (state.retryPending) {
            Text("Ответ ещё не получен. Повторите этот запрос или проверьте историю. Повтор не расходует дополнительный расклад.", color = CreamMuted)
        }
        Button(
            onClick = { focus.clearFocus(); viewModel.submit() }, modifier = Modifier.fillMaxWidth(),
            enabled = !state.submitting && state.question.isNotBlank() && (!state.manual || state.selectedIds.size == 3),
        ) { Text(if (state.retryPending) "Повторить запрос" else "Получить толкование") }
        Text("Расклад — повод для размышления. Решения остаются за вами.", color = CreamMuted, style = MaterialTheme.typography.bodySmall)
    }
}
