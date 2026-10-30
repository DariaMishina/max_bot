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
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.tooling.preview.Preview
import ru.tarotsphere.app.domain.model.*
import ru.tarotsphere.app.ui.theme.TarotSphereTheme
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.text.HtmlCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.tarotsphere.app.ui.components.*
import ru.tarotsphere.app.domain.validation.isMeaningfulQuestion

@Composable
private fun ReadingText(value: String) {
    val formatted = remember(value) {
        val plain = HtmlCompat.fromHtml(value.replace("\n", "<br>"), HtmlCompat.FROM_HTML_MODE_LEGACY).toString().trim()
        emphasizeReadingSections(plain)
    }
    SelectionContainer { Text(formatted, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurface) }
}

private val ReadingSectionHeader = Regex(
    """(?im)^\s*(Прошлое|Настоящее|Будущее|Общее толкование)(?:\s*([:—-])|\s*$)""",
)

internal fun emphasizeReadingSections(value: String): AnnotatedString {
    val builder = AnnotatedString.Builder(value)
    ReadingSectionHeader.findAll(value).forEach { match ->
        val title = match.groups[1] ?: return@forEach
        val separator = match.groups[2]
        builder.addStyle(
            SpanStyle(fontWeight = FontWeight.Bold),
            title.range.first,
            (separator?.range?.last ?: title.range.last) + 1,
        )
    }
    return builder.toAnnotatedString()
}

@Composable
fun ReadingScreen(viewModel: ReadingViewModel, onBack: () -> Unit, onNew: () -> Unit, onShop: () -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    BackHandler(onBack = onBack)
    LaunchedEffect(viewModel) { viewModel.refresh() }
    ReadingContent(state, onBack, onNew, onShop, viewModel::refresh, viewModel::question, viewModel::send)
}

@Composable
private fun ReadingContent(
    state: ReadingUiState, onBack: () -> Unit, onNew: () -> Unit, onShop: () -> Unit,
    onRefresh: () -> Unit, onQuestion: (String) -> Unit, onSend: () -> Unit,
) {
    val focus = LocalFocusManager.current
    val colors = MaterialTheme.colorScheme
    SphereScreen {
        TextButton(onClick = onBack, contentPadding = PaddingValues(horizontal = 0.dp, vertical = 12.dp)) {
            Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = null, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(8.dp))
            Text("Назад")
        }
        SphereHeader("Ваше толкование", "Три карты — один взгляд на вашу ситуацию", "Время прислушаться к себе")
        if (state.loading) LinearProgressIndicator(Modifier.fillMaxWidth(), color = colors.secondary)
        state.error?.let { StatusPanel("Не удалось обновить расклад", it, StatusTone.Error, onRefresh) }
        if (state.offline) StatusPanel("Сохранённый расклад", "Для новых уточняющих вопросов понадобится интернет.", onRetry = onRefresh)
        state.reading?.let { reading ->
            WorkshopSheet {
                Text("Ваш вопрос", style = MaterialTheme.typography.labelMedium, color = colors.secondary)
                Text(reading.question, style = MaterialTheme.typography.titleLarge)
            }
            WorkshopSheet {
                ReadingCards(reading.cards)
                WorkshopDivider()
                SectionHeading("Что говорят карты", "Персональная ИИ-интерпретация")
                ReadingText(reading.interpretation)
                Text("Решения остаются за вами.", style = MaterialTheme.typography.bodySmall, color = colors.onSurfaceVariant)
            }
            SphereHeader("Продолжим диалог?", "Уточните то, что важно именно вам", "Уточнения к раскладу")
            Text("Доступно вопросов: ${reading.followUpsRemaining}", style = MaterialTheme.typography.labelLarge, color = colors.secondary)
            reading.followUps.forEachIndexed { index, followUp ->
                WorkshopSheet {
                    Text("Ваш вопрос · ${index + 1}", style = MaterialTheme.typography.labelMedium, color = colors.secondary)
                    Text(followUp.question, style = MaterialTheme.typography.titleLarge, color = colors.primary)
                }
                WorkshopSheet(olive = true) {
                    Text("Ответ к раскладу", style = MaterialTheme.typography.labelMedium, color = colors.secondary)
                    ReadingText(followUp.answer)
                }
            }
            if (reading.followUpsRemaining > 0 || state.retryPending) {
                WorkshopSheet(olive = true) {
                    SectionHeading("Что ещё хочется понять?")
                    QuestionField(state.question, onQuestion, label = "Ваш уточняющий вопрос", minLines = 2,
                        enabled = !state.sending && !state.retryPending)
                    if (state.question.isNotBlank() && !isMeaningfulQuestion(state.question)) {
                        Text(
                            "Напишите уточнение словами.",
                            style = MaterialTheme.typography.bodySmall,
                            color = colors.error,
                        )
                    }
                    if (state.sending) StatusPanel("Готовим ответ…", tone = StatusTone.Progress)
                    state.followUpError?.let { StatusPanel("Не удалось получить ответ", it, StatusTone.Error) }
                    if (state.retryPending && !state.sending) StatusPanel("Можно повторить вопрос", "Повтор отправит тот же вопрос и не уменьшит доступное количество вопросов.")
                    PrimaryAction(
                        if (state.sending) "Готовим ответ…" else if (state.retryPending) "Повторить вопрос" else "Задать вопрос",
                        onClick = { focus.clearFocus(); onSend() }, enabled = !state.sending && isMeaningfulQuestion(state.question),
                        olive = true,
                    )
                }
            } else StatusPanel("Все уточняющие вопросы заданы", "Вы можете задать другой вопрос в новом раскладе.")
            SecondaryAction("Новый расклад", onNew)
            TextButton(onClick = onShop, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Купить расклады") }
        }
    }
}

@Composable
private fun ReadingCards(cards: List<TarotCard>) {
    val largeText = LocalDensity.current.fontScale > 1.3f
    if (largeText) {
        Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
            cards.forEachIndexed { index, card ->
                Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                    RevealedCard(card, Modifier.width(88.dp))
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        CardPosition(index)
                        Text(card.name, style = MaterialTheme.typography.titleMedium)
                    }
                }
            }
        }
    } else {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            cards.forEachIndexed { index, card ->
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    CardPosition(index)
                    RevealedCard(card)
                    Text(card.name, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

@Composable
private fun CardPosition(index: Int) {
    Text(listOf("Прошлое", "Настоящее", "Будущее").getOrElse(index) { "Карта" },
        style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.secondary)
}

@Composable
private fun RevealedCard(card: TarotCard, modifier: Modifier = Modifier) {
    val preview = LocalInspectionMode.current
    var revealed by remember(card.id) { mutableStateOf(preview) }
    LaunchedEffect(card.id) { revealed = true }
    TarotCardView(card, revealed, modifier)
}

@Preview(name = "Результат · 360", widthDp = 360, heightDp = 1000)
@Preview(name = "Результат · 412", widthDp = 412, heightDp = 1000)
@Preview(name = "Результат · 200%", widthDp = 360, heightDp = 1000, fontScale = 2f)
@Composable
private fun ReadingPreview() {
    TarotSphereTheme {
        ReadingContent(ReadingUiState(reading = Reading(
            1, "Что поможет мне двигаться вперёд и найти время для важного?",
            listOf(TarotCard("1", "Солнце", ""), TarotCard("2", "Луна", ""), TarotCard("3", "Звезда", "")),
            "Прошлое: Вспомните то, что уже помогало вам.\n\nНастоящее: Дайте себе время прислушаться к своим желаниям.\n\nБудущее: Начните с небольшого шага.",
            true, "2026-10-30", listOf(FollowUp("Как сделать первый шаг?", "Выберите небольшое действие, которое зависит от вас.")), 1,
        )), {}, {}, {}, {}, {}, {})
    }
}
