package ru.tarotsphere.app.ui.history

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.BorderStroke
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.tarotsphere.app.domain.model.HistoryItem
import ru.tarotsphere.app.ui.components.*

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
            Surface(color = MaterialTheme.colorScheme.secondaryContainer, shape = MaterialTheme.shapes.large) {
                Column(
                    Modifier.fillMaxWidth().padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    SphereEmblem(Modifier.size(72.dp), MaterialTheme.colorScheme.secondary)
                    Text("Здесь соберутся ваши расклады", style = MaterialTheme.typography.titleLarge)
                    Text(
                        "Первый вопрос станет началом личной истории наблюдений.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
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

@Composable
private fun HistoryRow(item: HistoryItem, onOpen: () -> Unit) {
    val colors = MaterialTheme.colorScheme
    Surface(
        modifier = Modifier.fillMaxWidth().clickable(role = Role.Button, onClickLabel = "Открыть расклад", onClick = onOpen),
        color = colors.surface,
        shape = MaterialTheme.shapes.large,
        border = BorderStroke(1.dp, colors.outlineVariant),
    ) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
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
            Text(item.question, style = MaterialTheme.typography.titleMedium, color = colors.onSurface)
            HorizontalDivider(color = colors.outlineVariant)
            Text("Открыть толкование  →", style = MaterialTheme.typography.labelLarge, color = colors.primary)
        }
    }
}
