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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.foundation.layout.Row
import androidx.compose.material3.Tab
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
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
import ru.tarotsphere.app.BuildConfig

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
    onPasswordMode: (Boolean) -> Unit = {},
    onRegistering: (Boolean) -> Unit = {},
    onLoginChange: (String) -> Unit = {},
    onPasswordChange: (String) -> Unit = {},
    onPasswordConfirmationChange: (String) -> Unit = {},
    onPasswordSubmit: () -> Unit = {},
    recoveryStart: suspend (String, String, String) -> String = { _, _, _ -> "" },
    recoveryConfirm: suspend (String, String, String) -> Unit = { _, _, _ -> },
) {
    var recovering by remember { mutableStateOf(false) }
    if (recovering) RecoveryForm(false, recoveryStart, recoveryConfirm) { recovering = false }
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
        if (BuildConfig.DEBUG) StatusPanel("Тестовая версия", "Отдельный тестовый аккаунт. Войдите по логину и паролю или email. Данные основной версии здесь не отображаются.")
        Spacer(Modifier.height(16.dp))
        SphereHeader(
            title = if (state.passwordMode) {
                if (state.registering) "Создайте своё пространство" else "С возвращением"
            } else if (state.codeSent) "Проверьте вашу почту" else "Сохраните свои расклады",
            subtitle = if (!state.passwordMode && state.codeSent) {
                "Мы отправили шестизначный код на ${state.email}. Он действует 10 минут."
            } else {
                "Аккаунт сохранит баланс и историю при переустановке или смене телефона."
            },
            eyebrow = "СФЕРА ТАРО",
        )
        if (state.passwordMode) {
            Row(Modifier.fillMaxWidth()) {
                Tab(selected = !state.registering, enabled = !state.submitting,
                    onClick = { onRegistering(false) }, text = { Text("Вход") }, modifier = Modifier.weight(1f))
                Tab(selected = state.registering, enabled = !state.submitting,
                    onClick = { onRegistering(true) }, text = { Text("Регистрация") }, modifier = Modifier.weight(1f))
            }
            if (state.registering) {
                StatusPanel("Сохраните логин и пароль",
                    "После регистрации подтвердите почту для восстановления в профиле. До этого сброс забытого пароля недоступен.",
                    StatusTone.Info)
                Text("Это отдельный аккаунт. Если у вас уже есть аккаунт через почту или VK ID, войдите прежним способом.",
                    style = MaterialTheme.typography.bodySmall)
            }
            OutlinedTextField(value = state.login, onValueChange = onLoginChange,
                shape = MaterialTheme.shapes.medium,
                label = { Text("Логин") },
                supportingText = {
                    Text("3–64: латинские буквы, цифры, _ . @ -; регистр не важен")
                },
                singleLine = true, enabled = !state.submitting, modifier = Modifier.fillMaxWidth())
            if (state.registering) {
                Text("Логин с @ не привязывает почту для восстановления.",
                    style = MaterialTheme.typography.bodySmall)
            }
            PasswordField(state.password, onPasswordChange, "Пароль", !state.submitting)
            if (state.registering) {
                Text("От 8 до 128 любых символов", style = MaterialTheme.typography.bodySmall)
                PasswordField(state.passwordConfirmation, onPasswordConfirmationChange, "Подтверждение пароля", !state.submitting)
            }
            PrimaryAction(if (state.registering) "Зарегистрироваться" else "Войти", onPasswordSubmit,
                enabled = !state.submitting)
            if (!state.registering) TextButton(onClick = { recovering = true }, enabled = !state.submitting) { Text("Забыли пароль?") }
            TextButton(onClick = { onPasswordMode(false) }, enabled = !state.submitting) {
                Text(if (BuildConfig.VK_AUTH_ENABLED) "Другие способы: почта или VK ID" else "Другой способ: почта")
            }
        } else if (!state.codeSent) {
            if (BuildConfig.VK_AUTH_ENABLED) SecondaryAction(
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
                    shape = MaterialTheme.shapes.medium,
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
            TextButton(onClick = { onPasswordMode(true) }, enabled = !state.submitting) { Text("Войти по логину и паролю") }
        } else {
            OutlinedTextField(
                shape = MaterialTheme.shapes.medium,
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
            "Продолжая, вы соглашаетесь с обработкой данных для создания аккаунта.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
fun PasswordField(value: String, onChange: (String) -> Unit, label: String, enabled: Boolean) {
    var visible by remember { mutableStateOf(false) }
    OutlinedTextField(value = value, onValueChange = onChange, label = { Text(label) },
        shape = MaterialTheme.shapes.medium,
        singleLine = true, enabled = enabled, modifier = Modifier.fillMaxWidth(),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
        visualTransformation = if (visible) VisualTransformation.None else PasswordVisualTransformation(),
        trailingIcon = {
            TextButton(onClick = { visible = !visible }, enabled = enabled) {
                Text(if (visible) "Скрыть" else "Показать")
            }
        })
}

@Preview(widthDp = 360, heightDp = 800, showBackground = true)
@Composable
private fun AuthPreview() {
    TarotSphereTheme {
        AuthScreen(SessionUiState(needsAuth = true), {}, {}, {}, {}, {}, {}, {}, {})
    }
}
