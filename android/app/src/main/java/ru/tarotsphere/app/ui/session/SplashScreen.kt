package ru.tarotsphere.app.ui.session

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import ru.tarotsphere.app.ui.components.BotanicalBackdrop
import ru.tarotsphere.app.ui.components.WorkshopBrand
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import ru.tarotsphere.app.R
import ru.tarotsphere.app.ui.theme.InkWine

@Composable
fun SplashScreen(
    state: SessionUiState,
    onRetry: () -> Unit,
) {
    BotanicalBackdrop {
        Column(
            modifier = Modifier.fillMaxSize().padding(32.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            WorkshopBrand(Modifier.size(132.dp))
            Spacer(Modifier.height(16.dp))
            Text(stringResource(R.string.app_name), style = MaterialTheme.typography.displaySmall, color = InkWine, textAlign = TextAlign.Center)
            Spacer(Modifier.height(8.dp))
            Text("Персональные расклады и история", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.secondary, textAlign = TextAlign.Center)
            Spacer(Modifier.height(32.dp))
            when {
                state.loading -> CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
                state.error != null -> {
                    Text(
                        state.error,
                        style = MaterialTheme.typography.bodyMedium,
                        textAlign = TextAlign.Center,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(16.dp))
                    Button(
                        onClick = onRetry,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.primary,
                            contentColor = MaterialTheme.colorScheme.onPrimary,
                        ),
                    ) {
                        Text("Повторить")
                    }
                }
            }
        }
    }
}
