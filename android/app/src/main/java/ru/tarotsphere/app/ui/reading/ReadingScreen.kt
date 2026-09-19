package ru.tarotsphere.app.ui.reading

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.unit.dp
import androidx.core.text.HtmlCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.tarotsphere.app.ui.components.*
import ru.tarotsphere.app.ui.theme.*

@Composable
private fun ReadingText(value: String) {
    val plain = remember(value) {
        // The existing API stores bot-era <b> tags. Preserve paragraph breaks.
        HtmlCompat.fromHtml(value.replace("\n", "<br>"), HtmlCompat.FROM_HTML_MODE_LEGACY).toString().trim()
    }
    SelectionContainer { Text(plain, style = MaterialTheme.typography.bodyLarge) }
}

@Composable
fun ReadingScreen(viewModel: ReadingViewModel, onBack: () -> Unit, onNew: () -> Unit, onShop: () -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val focus = LocalFocusManager.current
    BackHandler(onBack = onBack)
    LaunchedEffect(viewModel) { viewModel.refresh() }
    Column(
        Modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        TextButton(onClick = onBack) { Text("← Назад") }
        Text("Ваше толкование", style = MaterialTheme.typography.headlineMedium)
        if (state.loading) LinearProgressIndicator(Modifier.fillMaxWidth(), color = Gold)
        state.error?.let { ScreenMessage(it, viewModel::refresh) }
        if (state.offline) ScreenMessage("Сохранённый расклад. Для новых уточнений понадобится интернет.", viewModel::refresh)
        state.reading?.let { reading ->
            Text(reading.question, style = MaterialTheme.typography.titleLarge, color = Gold)
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                reading.cards.forEachIndexed { index, card ->
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(listOf("Прошлое", "Настоящее", "Будущее").getOrElse(index) { "Карта" }, style = MaterialTheme.typography.labelMedium, color = Gold)
                        var revealed by remember(card.id) { mutableStateOf(false) }
                        LaunchedEffect(card.id) { revealed = true }
                        TarotCardView(card, revealed)
                        Text(card.name, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            DeckCard { ReadingText(reading.interpretation) }
            Text("Уточнения", style = MaterialTheme.typography.titleLarge)
            reading.followUps.forEach { followUp ->
                DeckCard {
                    Text(followUp.question, style = MaterialTheme.typography.titleMedium, color = Gold)
                    Spacer(Modifier.height(10.dp))
                    ReadingText(followUp.answer)
                }
            }
            Text("Осталось уточнений: ${reading.followUpsRemaining}", color = CreamMuted)
            if (reading.followUpsRemaining > 0 || state.retryPending) {
                OutlinedTextField(
                    value = state.question, onValueChange = viewModel::question, label = { Text("Уточнить этот расклад") },
                    supportingText = { Text("${state.question.length}/1000") }, modifier = Modifier.fillMaxWidth(),
                    minLines = 2, maxLines = 5, enabled = !state.sending && !state.retryPending,
                )
                if (state.sending) { LinearProgressIndicator(Modifier.fillMaxWidth()); Text("Готовим ответ…", color = CreamMuted) }
                state.followUpError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                Button(onClick = { focus.clearFocus(); viewModel.send() }, enabled = !state.sending && state.question.isNotBlank(), modifier = Modifier.fillMaxWidth()) {
                    Text(if (state.retryPending) "Повторить уточнение" else "Задать уточнение")
                }
            } else {
                Text("Все уточнения к этому раскладу использованы. Вы можете задать другой вопрос в новом раскладе.", color = CreamMuted)
            }
            OutlinedButton(onClick = onNew, modifier = Modifier.fillMaxWidth()) { Text("Новый расклад") }
            TextButton(onClick = onShop) { Text("Купить расклады") }
        }
    }
}
