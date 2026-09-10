package ru.tarotsphere.app.ui.shop

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
fun ShopScreen(viewModel: ShopViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Магазин", style = MaterialTheme.typography.headlineMedium)
        Text(
            "Оплата RuStore Pay и ЮKassa подключается на этапе 5. Сейчас — каталог с сервера.",
            style = MaterialTheme.typography.bodyMedium,
        )
        when {
            state.loading -> CircularProgressIndicator(color = Gold, modifier = Modifier.padding(24.dp))
            state.error != null -> ScreenMessage(state.error!!, onRetry = viewModel::refresh)
            state.catalog != null -> {
                state.catalog!!.packages.forEach { pack ->
                    DeckCard {
                        Text(pack.name, style = MaterialTheme.typography.titleMedium, color = Gold)
                        Spacer(Modifier.height(4.dp))
                        Text("${pack.priceRub} ₽", style = MaterialTheme.typography.bodyLarge)
                    }
                }
                val methods = state.catalog!!.paymentMethods.joinToString(" · ")
                if (methods.isNotBlank()) {
                    Text("Способы: $methods", style = MaterialTheme.typography.bodyMedium, color = CreamMuted)
                }
            }
        }
    }
}
