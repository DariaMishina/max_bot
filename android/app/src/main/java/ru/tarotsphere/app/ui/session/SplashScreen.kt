package ru.tarotsphere.app.ui.session

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import ru.tarotsphere.app.ui.theme.CreamMuted
import ru.tarotsphere.app.ui.theme.Gold
import ru.tarotsphere.app.ui.theme.Ink
import ru.tarotsphere.app.ui.theme.Night

@Composable
fun SplashScreen(
    state: SessionUiState,
    onRetry: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Night)
            .padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("tarot sphere", style = MaterialTheme.typography.displaySmall, color = Gold)
        Spacer(Modifier.height(8.dp))
        Text("Расклады без входа", style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(32.dp))
        when {
            state.loading -> CircularProgressIndicator(color = Gold)
            state.error != null -> {
                Text(
                    state.error,
                    style = MaterialTheme.typography.bodyMedium,
                    textAlign = TextAlign.Center,
                    color = CreamMuted,
                )
                Spacer(Modifier.height(16.dp))
                Button(
                    onClick = onRetry,
                    colors = ButtonDefaults.buttonColors(containerColor = Gold, contentColor = Ink),
                ) {
                    Text("Повторить")
                }
            }
        }
    }
}
