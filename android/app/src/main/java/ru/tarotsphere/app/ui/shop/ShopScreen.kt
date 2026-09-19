package ru.tarotsphere.app.ui.shop

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.tarotsphere.app.domain.model.CatalogPackage
import ru.tarotsphere.app.ui.components.*
import ru.tarotsphere.app.ui.theme.*

@Composable
fun ShopScreen(viewModel: ShopViewModel, exhausted: Boolean = false) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var selectedId by rememberSaveable { mutableStateOf<String?>(null) }
    var consultation by rememberSaveable { mutableStateOf(false) }
    var notice by rememberSaveable { mutableStateOf<String?>(null) }
    val uriHandler = LocalUriHandler.current
    val selected = (if (consultation) state.catalog?.consultations else state.catalog?.packages)?.find { it.id == selectedId }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("Магазин", style = MaterialTheme.typography.headlineMedium)
        if (exhausted) DeckCard {
            Text("Бесплатные расклады закончились", style = MaterialTheme.typography.titleMedium, color = Gold)
            Spacer(Modifier.height(8.dp))
            Text("Ваша история сохранена. Здесь можно выбрать пакет для следующих вопросов.")
        }
        Text("Больше пространства для ваших вопросов", color = CreamMuted)
        Text("Покупки пока недоступны. Вы можете посмотреть пакеты и способы оплаты.", style = MaterialTheme.typography.bodyMedium)
        when {
            state.loading -> CircularProgressIndicator(color = Gold)
            state.error != null -> ScreenMessage(state.error!!, viewModel::refresh)
            state.catalog != null -> {
                val catalog = state.catalog!!
                if (catalog.packages.isEmpty()) Text("Пакеты пока не добавлены.")
                catalog.packages.forEach { pack ->
                    ProductCard(pack) { selectedId = pack.id; consultation = false }
                }
                Text("Лично с Дианой", style = MaterialTheme.typography.titleLarge, color = Gold)
                Text("Индивидуальная консультация с тарологом. Оплата картой через ЮKassa.", color = CreamMuted)
                catalog.consultations.forEach { pack ->
                    ProductCard(pack) { selectedId = pack.id; consultation = true }
                }
                OutlinedButton(onClick = {
                    val url = catalog.tarologistUrl
                    notice = if (url.isNullOrBlank() || !url.startsWith("https://")) {
                        "Контакт Дианы пока недоступен. Пожалуйста, попробуйте позже."
                    } else {
                        runCatching { uriHandler.openUri(url) }.exceptionOrNull()?.let { "Не удалось открыть контакт. Попробуйте позже." }
                    }
                }, modifier = Modifier.fillMaxWidth()) { Text("Написать Диане") }
            }
        }
    }
    if (selected != null) AlertDialog(
        onDismissRequest = { selectedId = null },
        title = { Text(selected.name) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("${selected.priceRub} ₽", style = MaterialTheme.typography.headlineSmall, color = Gold)
                Text("Выберите удобный способ. Покупки станут доступны позже.")
                if (!consultation && "rustore" in state.catalog!!.paymentMethods) Button(onClick = {
                    selectedId = null; notice = "Оплата в RuStore пока недоступна. Деньги не списаны."
                }, modifier = Modifier.fillMaxWidth()) { Text("Оплатить в RuStore") }
                if ("yookassa" in state.catalog!!.paymentMethods) OutlinedButton(onClick = {
                    selectedId = null; notice = "Оплата картой через ЮKassa пока недоступна. Деньги не списаны."
                }, modifier = Modifier.fillMaxWidth()) { Text("Оплатить картой (ЮKassa)") }
            }
        },
        confirmButton = { TextButton(onClick = { selectedId = null }) { Text("Закрыть") } },
    )
    notice?.let { message -> AlertDialog(
        onDismissRequest = { notice = null }, title = { Text("Пока недоступно") }, text = { Text(message) },
        confirmButton = { TextButton(onClick = { notice = null }) { Text("Понятно") } },
    ) }
}

@Composable
private fun ProductCard(pack: CatalogPackage, onChoose: () -> Unit) {
    DeckCard {
        Text(pack.name, style = MaterialTheme.typography.titleMedium, color = Gold)
        Spacer(Modifier.height(8.dp))
        Text("${pack.priceRub} ₽", style = MaterialTheme.typography.headlineSmall)
        if (pack.isSubscription) Text("Без ограничений на число раскладов в течение месяца", color = CreamMuted)
        Spacer(Modifier.height(8.dp))
        OutlinedButton(onClick = onChoose, modifier = Modifier.fillMaxWidth()) { Text("Выбрать") }
    }
}
