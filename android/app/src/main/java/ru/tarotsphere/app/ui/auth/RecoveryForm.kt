package ru.tarotsphere.app.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import ru.tarotsphere.app.ui.components.userMessage

@Composable
fun RecoveryForm(binding: Boolean, start: suspend (String, String, String) -> String,
                 confirm: suspend (String, String, String) -> Unit, close: () -> Unit) {
    var login by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var repeated by remember { mutableStateOf("") }
    var code by remember { mutableStateOf("") }
    var challenge by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var done by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    Dialog(onDismissRequest = { if (!busy) close() }) {
        Surface(shape = MaterialTheme.shapes.large) {
            Column(Modifier.imePadding().verticalScroll(rememberScrollState()).padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(if (binding) "Почта для восстановления" else "Восстановление пароля", style = MaterialTheme.typography.titleLarge)
                if (done) {
                    Text(if (binding) "Почта подтверждена. Теперь через неё можно восстановить пароль."
                         else "Пароль изменён. Все прежние сессии завершены. Войдите с новым паролем.")
                } else if (challenge.isEmpty()) {
                    Text(if (binding) "Укажите почту и текущий пароль. Затем подтвердите адрес кодом из письма."
                         else "Введите логин и почту, которую ранее подтвердили в профиле. Без привязанной почты сброс недоступен.")
                    if (!binding) OutlinedTextField(login, { login = it.take(32) }, label = { Text("Логин") }, enabled = !busy, singleLine = true)
                    OutlinedTextField(email, { email = it.take(320) }, label = { Text("Почта") }, enabled = !busy, singleLine = true)
                    if (binding) PasswordField(password, { password = it.take(128) }, "Текущий пароль", !busy)
                } else {
                    Text(if (binding) "Введите код из письма. Он действует 10 минут."
                         else "Если логин и подтверждённая почта совпадают, письмо отправлено. Код действует 10 минут.")
                    OutlinedTextField(code, { code = it.filter(Char::isDigit).take(6) }, label = { Text("Код из письма") }, enabled = !busy, singleLine = true)
                    if (!binding) {
                        PasswordField(password, { password = it.take(128) }, "Новый пароль (12–128 символов)", !busy)
                        PasswordField(repeated, { repeated = it.take(128) }, "Повторите пароль", !busy)
                    }
                }
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                if (!done) Button(enabled = !busy, onClick = {
                    error = null
                    if (challenge.isNotEmpty() && !binding && (password != repeated || password.length !in 12..128)) {
                        error = "Пароли должны совпадать и содержать 12–128 символов"
                    } else {
                        busy = true
                        scope.launch {
                            try {
                                if (challenge.isEmpty()) challenge = start(login, email, password)
                                else { confirm(challenge, code, password); done = true }
                                password = ""; repeated = ""
                            } catch (e: CancellationException) { throw e
                            } catch (e: Exception) { error = e.userMessage()
                            } finally { busy = false }
                        }
                    }
                }) { Text(if (busy) "Подождите…" else if (challenge.isEmpty()) "Получить код" else "Подтвердить") }
                if (!done && challenge.isNotEmpty()) TextButton(enabled = !busy, onClick = {
                    challenge = ""; code = ""; password = ""; repeated = ""; error = null
                }) { Text("Запросить новый код / изменить данные") }
                TextButton(enabled = !busy, onClick = close) { Text(if (done) "Готово" else "Закрыть") }
            }
        }
    }
}
