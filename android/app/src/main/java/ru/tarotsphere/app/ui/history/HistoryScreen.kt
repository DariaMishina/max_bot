package ru.tarotsphere.app.ui.history

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowRight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.tarotsphere.app.domain.model.HistoryItem
import ru.tarotsphere.app.ui.components.*
import ru.tarotsphere.app.ui.theme.InkWine

@Composable
fun HistoryScreen(viewModel: HistoryViewModel, onOpen: (Long) -> Unit, onNew: () -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(viewModel) { viewModel.refresh() }
    SphereLazyScreen {
        item {
            SphereHeader(
                title = "История",
                subtitle = "Возвращайтесь к вопросам, которые уже открывали вместе с картами.",
                eyebrow = "Ваш путь",
            )
        }
        item {
            TextButton(
                onClick = viewModel::refresh,
                enabled = !state.loading,
                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
            ) { Text("Обновить историю") }
        }
        if (state.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.secondary) }
        state.error?.let { error -> item {
            StatusPanel(
                "Не удалось обновить историю",
                if (state.items.isEmpty()) error else "$error Показаны сохранённые расклады.",
                StatusTone.Error,
                viewModel::refresh,
            )
        } }
        if (!state.loading && state.items.isEmpty()) item {
            WorkshopSheet(olive = true) {
                Column(
                    Modifier.fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    SphereEmblem(Modifier.size(72.dp), MaterialTheme.colorScheme.secondary)
                    Text("Здесь соберутся ваши расклады", Modifier.fillMaxWidth(), textAlign = TextAlign.Center, style = MaterialTheme.typography.titleLarge, color = InkWine)
                    Text(
                        "Первый вопрос станет началом личной истории наблюдений.",
                        Modifier.fillMaxWidth(),
                        textAlign = TextAlign.Center,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                    PrimaryAction("Сделать первый расклад", onNew)
                }
            }
        }
        if (state.items.isNotEmpty()) item {
            SectionHeading("Сохранённые расклады", "Новые записи появляются здесь автоматически.")
        }
        items(state.items, key = { it.id }) { item ->
            HistoryRow(item) { onOpen(item.id) }
        }
        if (state.nextBeforeId != null) item {
            SecondaryAction("Показать более ранние", viewModel::loadMore, enabled = !state.loading)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun HistoryRow(item: HistoryItem, onOpen: () -> Unit) {
    val colors = MaterialTheme.colorScheme
    WorkshopSheet(Modifier.padding(vertical = 6.dp), onClick = onOpen, onClickLabel = "Открыть расклад") {
        FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(displayDate(item.createdAt), style = MaterialTheme.typography.labelMedium, color = colors.secondary)
            Surface(color = colors.surfaceVariant, shape = MaterialTheme.shapes.small) {
                Text(
                    if (item.isFree) "Подарочный" else item.type,
                    Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                    style = MaterialTheme.typography.bodySmall,
                    color = colors.onSurfaceVariant,
                )
            }
        }
        Text(item.question, style = MaterialTheme.typography.titleLarge, color = InkWine)
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("Открыть толкование", Modifier.weight(1f), style = MaterialTheme.typography.labelLarge, color = colors.primary)
            Icon(Icons.AutoMirrored.Outlined.KeyboardArrowRight, contentDescription = null, tint = colors.primary)
        }
    }
}
