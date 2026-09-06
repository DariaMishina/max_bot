package ru.tarotsphere.app.ui.spread

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
import ru.tarotsphere.app.ui.theme.CreamMuted
import ru.tarotsphere.app.ui.theme.Gold

@Composable
fun SpreadScreen(viewModel: SpreadViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Расклад", style = MaterialTheme.typography.headlineMedium)
        Text(
            "Вопрос и выбор карт появятся на этапе 4. Сейчас приложение уже ходит в API как гость.",
            style = MaterialTheme.typography.bodyMedium,
        )
        when {
            state.loading -> CircularProgressIndicator(color = Gold, modifier = Modifier.padding(24.dp))
            state.error != null -> ScreenMessage(state.error!!)
            state.balance != null -> {
                val b = state.balance!!
                DeckCard {
                    Text("Баланс на этом телефоне", style = MaterialTheme.typography.titleMedium, color = Gold)
                    Spacer(Modifier.height(8.dp))
                    Text("Бесплатных: ${b.freeRemaining}", style = MaterialTheme.typography.bodyLarge)
                    Text("Купленных: ${b.paidRemaining}", style = MaterialTheme.typography.bodyLarge)
                    Text(
                        "Гостевая сессия создана автоматически — экрана входа нет.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = CreamMuted,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                }
            }
        }
    }
}
