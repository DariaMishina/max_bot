package ru.tarotsphere.app.ui.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.vk.id.AccessToken
import com.vk.id.VKID
import com.vk.id.VKIDAuthFail
import com.vk.id.auth.VKIDAuthCallback
import ru.tarotsphere.app.ui.components.PrimaryAction
import ru.tarotsphere.app.ui.components.SecondaryAction
import ru.tarotsphere.app.ui.components.SphereHeader
import ru.tarotsphere.app.ui.components.SphereScreen
import ru.tarotsphere.app.ui.components.StatusPanel
import ru.tarotsphere.app.ui.components.StatusTone
import ru.tarotsphere.app.ui.session.SessionUiState
import ru.tarotsphere.app.ui.theme.TarotSphereTheme

@Composable
fun AuthScreen(
    state: SessionUiState,
    onEmailChange: (String) -> Unit,
    onCodeChange: (String) -> Unit,
    onRequestCode: () -> Unit,
    onConfirm: () -> Unit,
    onChangeEmail: () -> Unit,
    onVkStart: () -> Unit,
    onVkToken: (String) -> Unit,
    onVkFailure: (String?) -> Unit,
) {
    val lifecycleOwner = LocalLifecycleOwner.current
    val vkCallback = remember(onVkToken, onVkFailure) {
        object : VKIDAuthCallback {
            override fun onAuth(accessToken: AccessToken) {
                onVkToken(accessToken.token)
            }

            override fun onFail(fail: VKIDAuthFail) {
                onVkFailure(
                    if (fail is VKIDAuthFail.Canceled) null
                    else "Не удалось войти через VK ID. Попробуйте ещё раз.",
                )
            }
        }
    }
    SphereScreen {
        Spacer(Modifier.height(16.dp))
        SphereHeader(
            title = if (state.codeSent) "Введите код из письма" else "Войти или создать аккаунт",
            subtitle = if (state.codeSent) {
                "Мы отправили шестизначный код на ${state.email}. Он действует 10 минут."
            } else {
                "Аккаунт сохранит баланс и историю при переустановке или смене телефона."
            },
            eyebrow = "СФЕРА ТАРО",
        )
        if (!state.codeSent) {
            SecondaryAction(
                text = "Продолжить через VK ID",
                onClick = {
                    onVkStart()
                    VKID.instance.authorize(lifecycleOwner, vkCallback)
                },
                enabled = !state.submitting,
            )
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Или продолжите по email", style = MaterialTheme.typography.titleMedium)
                OutlinedTextField(
                    value = state.email,
                    onValueChange = onEmailChange,
                    label = { Text("Электронная почта") },
                    singleLine = true,
                    enabled = !state.submitting,
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Email,
                        imeAction = ImeAction.Done,
                    ),
                    modifier = Modifier.fillMaxWidth(),
                )
                PrimaryAction("Получить код", onRequestCode, enabled = !state.submitting)
            }
        } else {
            OutlinedTextField(
                value = state.code,
                onValueChange = onCodeChange,
                label = { Text("Код из письма") },
                supportingText = { Text("6 цифр") },
                singleLine = true,
                enabled = !state.submitting,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.NumberPassword,
                    imeAction = ImeAction.Done,
                ),
                modifier = Modifier.fillMaxWidth(),
            )
            PrimaryAction("Войти", onConfirm, enabled = !state.submitting && state.code.length == 6)
            TextButton(onClick = onChangeEmail, enabled = !state.submitting) { Text("Изменить почту") }
        }
        if (state.submitting) StatusPanel("Проверяем…", tone = StatusTone.Progress)
        state.error?.let { StatusPanel("Не получилось", it, StatusTone.Error) }
        Text(
            "Продолжая, вы соглашаетесь с обработкой данных для создания аккаунта. Пароль создавать не нужно.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Preview(widthDp = 360, heightDp = 800, showBackground = true)
@Composable
private fun AuthPreview() {
    TarotSphereTheme {
        AuthScreen(SessionUiState(needsAuth = true), {}, {}, {}, {}, {}, {}, {}, {})
    }
}
