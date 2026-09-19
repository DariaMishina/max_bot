package ru.tarotsphere.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import ru.tarotsphere.app.ui.theme.GoldDim
import ru.tarotsphere.app.ui.theme.NightCard

@Composable
fun DeckCard(
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(20.dp))
            .background(NightCard)
            .border(1.dp, GoldDim.copy(alpha = 0.45f), RoundedCornerShape(20.dp))
            .padding(20.dp),
    ) {
        content()
    }
}

@Composable
fun ScreenMessage(
    text: String,
    onRetry: (() -> Unit)? = null,
) {
    Column(modifier = Modifier.padding(horizontal = 8.dp, vertical = 16.dp)) {
        Text(text = text, style = MaterialTheme.typography.bodyMedium)
        if (onRetry != null) {
            Spacer(Modifier.height(8.dp))
            TextButton(onClick = onRetry) {
                Text("Повторить")
            }
        }
    }
}
