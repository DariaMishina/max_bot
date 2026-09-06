package ru.tarotsphere.app.ui.profile

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
fun ProfileScreen(viewModel: ProfileViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Профиль", style = MaterialTheme.typography.headlineMedium)
        when {
            state.loading -> CircularProgressIndicator(color = Gold, modifier = Modifier.padding(24.dp))
            state.error != null -> ScreenMessage(state.error!!)
            state.profile != null -> {
                val p = state.profile!!
                DeckCard {
                    Text(if (p.isGuest) "Гость" else "Аккаунт", style = MaterialTheme.typography.titleMedium, color = Gold)
                    Spacer(Modifier.height(8.dp))
                    Text("id: ${p.userId.take(8)}…", style = MaterialTheme.typography.bodyMedium)
                    Spacer(Modifier.height(12.dp))
                    Text("Бесплатных раскладов: ${p.balance.freeRemaining}", style = MaterialTheme.typography.bodyLarge)
                    Text("Купленных: ${p.balance.paidRemaining}", style = MaterialTheme.typography.bodyLarge)
                }
                DeckCard {
                    Text("Об этом телефоне", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "Расклады привязаны к устройству. Вход через VK, Яндекс или почту появится позже. Регистрации в этой версии нет.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = CreamMuted,
                    )
                }
            }
        }
    }
}
