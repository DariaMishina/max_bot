package ru.tarotsphere.app.ui.reading

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.unit.dp
import androidx.core.text.HtmlCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.tarotsphere.app.ui.components.*

@Composable
private fun ReadingText(value: String) {
    val plain = remember(value) {
        HtmlCompat.fromHtml(value.replace("\n", "<br>"), HtmlCompat.FROM_HTML_MODE_LEGACY).toString().trim()
    }
    SelectionContainer { Text(plain, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurface) }
}

@Composable
fun ReadingScreen(viewModel: ReadingViewModel, onBack: () -> Unit, onNew: () -> Unit, onShop: () -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val focus = LocalFocusManager.current
    BackHandler(onBack = onBack)
    LaunchedEffect(viewModel) { viewModel.refresh() }
    val colors = MaterialTheme.colorScheme
    SphereScreen {
        TextButton(onClick = onBack, contentPadding = PaddingValues(horizontal = 0.dp, vertical = 12.dp)) {
            Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = null, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(8.dp))
            Text("Назад")
        }
        SphereHeader("Ваше толкование", eyebrow = "Время прислушаться к себе")
        if (state.loading) LinearProgressIndicator(Modifier.fillMaxWidth(), color = colors.secondary)
        state.error?.let { StatusPanel("Не удалось обновить расклад", it, StatusTone.Error, viewModel::refresh) }
        if (state.offline) StatusPanel("Сохранённый расклад", "Для новых уточнений понадобится интернет.", onRetry = viewModel::refresh)
        state.reading?.let { reading ->
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Ваш вопрос", style = MaterialTheme.typography.labelMedium, color = colors.secondary)
                Text(reading.question, style = MaterialTheme.typography.titleLarge)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                reading.cards.forEachIndexed { index, card ->
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(listOf("Прошлое", "Настоящее", "Будущее").getOrElse(index) { "Карта" }, style = MaterialTheme.typography.labelMedium, color = colors.secondary)
                        var revealed by remember(card.id) { mutableStateOf(false) }
                        LaunchedEffect(card.id) { revealed = true }
                        TarotCardView(card, revealed)
                        Text(card.name, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            HorizontalDivider(color = colors.outlineVariant)
            ReadingText(reading.interpretation)
            HorizontalDivider(color = colors.outlineVariant)
            SphereHeader("Продолжим размышлять?", "Осталось уточнений: ${reading.followUpsRemaining}")
            reading.followUps.forEachIndexed { index, followUp ->
                Surface(color = colors.surface, shape = MaterialTheme.shapes.large) {
                    Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text("Уточнение ${index + 1}", style = MaterialTheme.typography.labelMedium, color = colors.secondary)
                        Text(followUp.question, style = MaterialTheme.typography.titleMedium, color = colors.primary)
                        ReadingText(followUp.answer)
                    }
                }
            }
            if (reading.followUpsRemaining > 0 || state.retryPending) {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    QuestionField(state.question, viewModel::question, label = "Уточнить этот расклад", minLines = 2,
                        enabled = !state.sending && !state.retryPending)
                    if (state.sending) StatusPanel("Готовим ответ…", tone = StatusTone.Progress)
                    state.followUpError?.let { StatusPanel("Не удалось получить уточнение", it, StatusTone.Error) }
                    if (state.retryPending && !state.sending) StatusPanel("Можно повторить уточнение", "Повтор отправит тот же вопрос и не расходует дополнительное уточнение.")
                    PrimaryAction(
                        if (state.sending) "Готовим ответ…" else if (state.retryPending) "Повторить уточнение" else "Задать уточнение",
                        onClick = { focus.clearFocus(); viewModel.send() }, enabled = !state.sending && state.question.isNotBlank(),
                    )
                }
            } else StatusPanel("Все уточнения использованы", "Вы можете задать другой вопрос в новом раскладе.")
            SecondaryAction("Новый расклад", onNew)
            TextButton(onClick = onShop, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Купить расклады") }
        }
    }
}
