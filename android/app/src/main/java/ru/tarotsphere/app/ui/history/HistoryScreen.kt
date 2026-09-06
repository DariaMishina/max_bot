package ru.tarotsphere.app.ui.history

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.tarotsphere.app.ui.components.DeckCard
import ru.tarotsphere.app.ui.components.ScreenMessage
import ru.tarotsphere.app.ui.theme.Gold

@Composable
fun HistoryScreen(viewModel: HistoryViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    Column(modifier = Modifier.fillMaxSize()) {
        Text(
            "История",
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(start = 20.dp, top = 20.dp, end = 20.dp),
        )
        when {
            state.loading -> CircularProgressIndicator(color = Gold, modifier = Modifier.padding(24.dp))
            state.error != null -> ScreenMessage(state.error!!)
            state.items.isEmpty() -> ScreenMessage("Пока нет раскладов. Они появятся здесь после гадания.")
            else -> LazyColumn(
                contentPadding = PaddingValues(20.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                items(state.items, key = { it.id }) { item ->
                    DeckCard {
                        Text(item.question.ifBlank { "Без вопроса" }, style = MaterialTheme.typography.titleMedium)
                        Spacer(Modifier.height(6.dp))
                        Text(item.createdAt, style = MaterialTheme.typography.bodyMedium)
                    }
                }
            }
        }
    }
}
