package ru.tarotsphere.app.ui.history

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.tarotsphere.app.ui.components.*
import ru.tarotsphere.app.ui.theme.*

@Composable
fun HistoryScreen(viewModel: HistoryViewModel, onOpen: (Long) -> Unit, onNew: () -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(viewModel) { viewModel.refresh() }
    LazyColumn(
        Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text("История", style = MaterialTheme.typography.headlineMedium)
            Text("Ваши вопросы и подсказки карт", color = CreamMuted)
            TextButton(onClick = viewModel::refresh, enabled = !state.loading) { Text("Обновить") }
        }
        if (state.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth(), color = Gold) }
        state.error?.let { error -> item {
            ScreenMessage(if (state.items.isEmpty()) error else "$error Показана сохранённая история.", viewModel::refresh)
        } }
        if (!state.loading && state.items.isEmpty()) item {
            DeckCard {
                Text("Здесь будет ваша история", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
                Text("Задайте первый вопрос. Готовый расклад сохранится автоматически.", color = CreamMuted)
                TextButton(onClick = onNew) { Text("Сделать расклад") }
            }
        }
        items(state.items, key = { it.id }) { item ->
            DeckCard(Modifier.clickable(role = Role.Button, onClickLabel = "Открыть расклад") { onOpen(item.id) }) {
                Text(item.question, style = MaterialTheme.typography.titleMedium, color = Gold)
                Spacer(Modifier.height(8.dp))
                Text(displayDate(item.createdAt), style = MaterialTheme.typography.bodySmall, color = CreamMuted)
                Spacer(Modifier.height(8.dp))
                Text("Читать расклад →", style = MaterialTheme.typography.labelLarge)
            }
        }
        if (state.nextBeforeId != null) item {
            OutlinedButton(onClick = viewModel::loadMore, enabled = !state.loading, modifier = Modifier.fillMaxWidth()) { Text("Загрузить ещё") }
        }
    }
}
