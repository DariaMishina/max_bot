package ru.tarotsphere.app.ui.profile

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.tarotsphere.app.ui.components.*

@Composable
fun ProfileScreen(viewModel: ProfileViewModel, onDeleted: () -> Unit, onShop: () -> Unit) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var confirmDelete by rememberSaveable { mutableStateOf(false) }
    LaunchedEffect(viewModel) { viewModel.refresh() }
    LaunchedEffect(state.deleted) { if (state.deleted) onDeleted() }
    SphereScreen {
        SphereHeader(
            title = "Ваше пространство",
            subtitle = "Баланс, связь с поддержкой и управление данными — в одном месте.",
            eyebrow = "Профиль",
        )
        if (state.loading) LinearProgressIndicator(Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.secondary)
        state.error?.let { StatusPanel("Не удалось обновить профиль", it, StatusTone.Error, viewModel::refresh) }
        state.profile?.let { profile ->
            BalanceSummary(
                freeRemaining = profile.balance.freeRemaining,
                paidRemaining = profile.balance.paidRemaining,
                totalUsed = profile.balance.totalUsed,
                unlimitedText = if (profile.balance.hasUnlimited) "До ${displayDate(profile.balance.unlimitedUntil.orEmpty())}" else null,
                offline = state.offline,
                onShop = onShop,
                onRefresh = viewModel::refresh,
                actionsEnabled = !state.loading && !state.deleting,
            )
        }
        StatusPanel(
            "Тестовый гостевой профиль",
            "Пока вход ещё не подключён, история и баланс доступны в этой установке приложения. Восстановление через VK ID и email появится перед выпуском.",
        )
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            SectionHeading("Помогите сделать Сферу лучше", "Расскажите, что оказалось полезным, непонятным или лишним.")
            OutlinedTextField(
                value = state.feedback, onValueChange = viewModel::feedback, label = { Text("Сообщение") },
                supportingText = { Text("${state.feedback.length}/2000") }, minLines = 3, maxLines = 6,
                modifier = Modifier.fillMaxWidth(), enabled = !state.sending && !state.deleting,
                shape = MaterialTheme.shapes.medium,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedContainerColor = MaterialTheme.colorScheme.surface,
                    unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                ),
            )
            state.feedbackMessage?.let { StatusPanel("Обратная связь", it) }
            PrimaryAction(
                if (state.sending) "Отправляем…" else "Отправить сообщение",
                viewModel::sendFeedback,
                enabled = state.feedback.isNotBlank() && !state.sending && !state.deleting,
            )
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            SectionHeading("Управление данными", "Удаление затронет гостевой профиль, историю, сообщения и оставшиеся расклады.")
            state.deleteError?.let { StatusPanel("Не удалось удалить данные", it, StatusTone.Error) }
            OutlinedButton(
                onClick = { confirmDelete = true },
                enabled = !state.deleting && !state.sending && !state.loading,
                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error),
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.error),
                shape = MaterialTheme.shapes.medium,
            ) {
                Text(if (state.deleting) "Удаляем…" else "Удалить данные профиля")
            }
        }
    }
    if (confirmDelete) AlertDialog(
        onDismissRequest = { confirmDelete = false },
        title = { Text("Удалить все данные?") },
        text = { Text("История, уточняющие вопросы, сообщения обратной связи и оставшиеся расклады будут удалены с сервера и этого телефона. Это действие нельзя отменить.") },
        confirmButton = { TextButton(onClick = { confirmDelete = false; viewModel.deleteData() }) { Text("Удалить навсегда", color = MaterialTheme.colorScheme.error) } },
        dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Отмена") } },
    )
}
