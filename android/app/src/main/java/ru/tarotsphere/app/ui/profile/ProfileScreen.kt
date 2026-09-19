package ru.tarotsphere.app.ui.profile

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.tarotsphere.app.ui.components.*
import ru.tarotsphere.app.ui.theme.*

@Composable
fun ProfileScreen(viewModel: ProfileViewModel, onDeleted: () -> Unit, onShop: () -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var confirmDelete by rememberSaveable { mutableStateOf(false) }
    LaunchedEffect(viewModel) { viewModel.refresh() }
    LaunchedEffect(state.deleted) { if (state.deleted) onDeleted() }
    Column(Modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("Профиль", style = MaterialTheme.typography.headlineMedium)
        if (state.loading) LinearProgressIndicator(Modifier.fillMaxWidth(), color = Gold)
        state.error?.let { ScreenMessage(it, viewModel::refresh) }
        state.profile?.let { profile ->
            DeckCard {
                Text("Вы — гость", style = MaterialTheme.typography.titleLarge, color = Gold)
                Spacer(Modifier.height(12.dp))
                Text("Бесплатных раскладов: ${profile.balance.freeRemaining}")
                Text("Купленных: ${profile.balance.paidRemaining}")
                if (profile.balance.hasUnlimited) Text("Безлимит до ${displayDate(profile.balance.unlimitedUntil.orEmpty())}")
                Text("Всего раскладов: ${profile.balance.totalUsed}", color = CreamMuted)
                if (state.offline) Text("Сохранённый баланс. Обновится при подключении к интернету.", color = CreamMuted)
                Column {
                    TextButton(onClick = onShop, enabled = !state.deleting) { Text("Купить расклады") }
                    TextButton(onClick = viewModel::refresh, enabled = !state.loading && !state.deleting) { Text("Обновить") }
                }
            }
        }
        DeckCard {
            Text("На этом телефоне", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            Text("Расклады, баланс и история привязаны к этому телефону. Если удалить приложение или сменить телефон, доступ к ним потеряется. Вход через VK, Яндекс и почту появится позже.", color = CreamMuted)
        }
        DeckCard {
            Text("Обратная связь", style = MaterialTheme.typography.titleMedium, color = Gold)
            Spacer(Modifier.height(8.dp))
            Text("Расскажите, что вам понравилось или что стоит исправить.", color = CreamMuted)
            OutlinedTextField(
                value = state.feedback, onValueChange = viewModel::feedback, label = { Text("Сообщение") },
                supportingText = { Text("${state.feedback.length}/2000") }, minLines = 3, maxLines = 6,
                modifier = Modifier.fillMaxWidth(), enabled = !state.sending && !state.deleting,
            )
            state.feedbackMessage?.let { Text(it) }
            Button(onClick = viewModel::sendFeedback, enabled = state.feedback.isNotBlank() && !state.sending && !state.deleting) {
                Text(if (state.sending) "Отправляем…" else "Отправить")
            }
        }
        DeckCard {
            Text("Удаление данных", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            Text("Можно удалить гостевой профиль, историю и баланс. Восстановить их будет нельзя.", color = CreamMuted)
            state.deleteError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            TextButton(onClick = { confirmDelete = true }, enabled = !state.deleting && !state.sending && !state.loading) {
                Text(if (state.deleting) "Удаляем…" else "Удалить мои данные", color = MaterialTheme.colorScheme.error)
            }
        }
    }
    if (confirmDelete) AlertDialog(
        onDismissRequest = { confirmDelete = false },
        title = { Text("Удалить все данные?") },
        text = { Text("История, уточнения, сообщения обратной связи и оставшиеся расклады будут удалены с сервера и этого телефона. Это действие нельзя отменить.") },
        confirmButton = { TextButton(onClick = { confirmDelete = false; viewModel.deleteData() }) { Text("Удалить навсегда", color = MaterialTheme.colorScheme.error) } },
        dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Отмена") } },
    )
}
