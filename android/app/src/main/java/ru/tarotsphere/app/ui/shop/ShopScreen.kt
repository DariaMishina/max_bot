package ru.tarotsphere.app.ui.shop

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ru.tarotsphere.app.BuildConfig
import ru.tarotsphere.app.ui.components.*

@Composable
fun ShopScreen(viewModel: ShopViewModel, exhausted: Boolean = false) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var selectedId by rememberSaveable { mutableStateOf<String?>(null) }
    var consultation by rememberSaveable { mutableStateOf(false) }
    var notice by rememberSaveable { mutableStateOf<String?>(null) }
    val uriHandler = LocalUriHandler.current
    val selected = (if (consultation) state.catalog?.consultations else state.catalog?.packages)?.find { it.id == selectedId }
    SphereScreen {
        SphereHeader(
            title = "Продолжите знакомство",
            subtitle = if (BuildConfig.DEBUG) {
                "Выберите запас раскладов или личную встречу с тарологом."
            } else {
                "Выберите запас раскладов для самостоятельного диалога с картами."
            },
            eyebrow = "Магазин",
        )
        if (exhausted) StatusPanel(
            "Доступные расклады закончились",
            "Все готовые толкования сохранены в истории. Здесь можно выбрать продолжение.",
        )
        if (!BuildConfig.RUSTORE_BILLING_CONFIGURED) StatusPanel(
            "Просмотр тестового магазина",
            "Пакеты можно посмотреть, но оплата в этой сборке отключена.",
        )
        if (state.catalog?.billingEnabled == false) StatusPanel(
            "Оплата готовится к запуску",
            "Покупки временно недоступны. Готовые расклады можно перечитать в истории.",
        )
        when {
            state.loading -> LinearProgressIndicator(Modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.secondary)
            state.error != null -> StatusPanel("Не удалось загрузить магазин", state.error, StatusTone.Error, viewModel::refresh)
            state.catalog != null -> {
                val catalog = state.catalog!!
                SectionHeading("Расклады", "Для самостоятельного диалога с картами в удобное время.")
                if (catalog.packages.isEmpty()) StatusPanel("Пакеты пока не добавлены")
                catalog.packages.forEach { pack ->
                    PackageCard(
                        title = pack.name,
                        price = "${pack.priceRub} ₽",
                        emphasized = pack.isSubscription,
                        description = if (pack.isSubscription) "Без ограничений на число раскладов в течение месяца" else "Сохраняются в вашем балансе",
                    ) { selectedId = pack.id; consultation = false }
                }
                if (BuildConfig.DEBUG) {
                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    SectionHeading("Лично с Дианой", "Индивидуальная консультация с тарологом и вниманием к вашей ситуации.")
                    catalog.consultations.forEach { pack ->
                        PackageCard(
                            title = pack.name,
                            price = "${pack.priceRub} ₽",
                            description = "Оплата картой через ЮKassa",
                            action = "Выбрать консультацию",
                            emphasized = true,
                        ) { selectedId = pack.id; consultation = true }
                    }
                    Surface(color = MaterialTheme.colorScheme.surfaceVariant, shape = MaterialTheme.shapes.large) {
                        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            Text("Только для проверки", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.secondary)
                            Text(
                                "В debug-сборке контакт открывается без оплаты. В обычной версии он появится только после подтверждённой покупки консультации.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            SecondaryAction("Написать Диане — тест", onClick = {
                                val url = catalog.tarologistUrl
                                notice = if (url.isNullOrBlank() || !url.startsWith("https://")) {
                                    "Контакт Дианы пока недоступен. Пожалуйста, попробуйте позже."
                                } else {
                                    runCatching { uriHandler.openUri(url) }.exceptionOrNull()?.let { "Не удалось открыть контакт. Попробуйте позже." }
                                }
                            })
                        }
                    }
                }
            }
        }
    }
    if (selected != null) AlertDialog(
        onDismissRequest = { selectedId = null },
        title = { Text(selected.name) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("${selected.priceRub} ₽", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
                Text(if (BuildConfig.RUSTORE_BILLING_CONFIGURED)
                    "Оплата проходит в RuStore. После подтверждения покупки расклады появятся на вашем балансе."
                else "В этой тестовой сборке покупки отключены. Деньги не списываются.")
                if (!consultation && BuildConfig.RUSTORE_BILLING_CONFIGURED && "rustore" in state.catalog!!.paymentMethods) Button(onClick = {
                    selectedId = null
                    viewModel.buy(selected.id)
                }, enabled = state.purchasingId == null, modifier = Modifier.fillMaxWidth()) {
                    Text(if (state.purchasingId == selected.id) "Проверяем…" else "Оплатить в RuStore")
                }
                if (consultation) Text(
                    "Оплата консультаций появится позже через ЮKassa.",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        },
        confirmButton = { TextButton(onClick = { selectedId = null }) { Text("Закрыть") } },
    )
    notice?.let { message -> AlertDialog(
        onDismissRequest = { notice = null }, title = { Text("Пока недоступно") }, text = { Text(message) },
        confirmButton = { TextButton(onClick = { notice = null }) { Text("Понятно") } },
    ) }
    state.paymentMessage?.let { message -> AlertDialog(
        onDismissRequest = viewModel::consumePaymentMessage,
        title = { Text("Оплата RuStore") },
        text = { Text(message) },
        confirmButton = {
            if (state.canRetryVerification) TextButton(onClick = viewModel::retryVerification) { Text("Проверить ещё раз") }
            else TextButton(onClick = viewModel::consumePaymentMessage) { Text("Понятно") }
        },
        dismissButton = if (state.canRetryVerification) {
            { TextButton(onClick = viewModel::consumePaymentMessage) { Text("Позже") } }
        } else null,
    ) }
}
