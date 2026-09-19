package ru.tarotsphere.app.ui.components

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import coil.compose.SubcomposeAsyncImage
import ru.tarotsphere.app.domain.model.TarotCard
import ru.tarotsphere.app.ui.theme.*

@Composable
fun TarotCardView(
    card: TarotCard, revealed: Boolean, modifier: Modifier = Modifier,
    selection: Int? = null, onClick: (() -> Unit)? = null, enabled: Boolean = true,
) {
    val rotation by animateFloatAsState(if (revealed) 180f else 0f, tween(450), label = "cardFlip")
    Column(modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        Box(
            Modifier.fillMaxWidth().aspectRatio(0.62f)
                .graphicsLayer { rotationY = rotation; cameraDistance = 12 * density }
                .clip(RoundedCornerShape(12.dp)).background(NightCard)
                .border(if (selection != null) 2.dp else 1.dp, if (selection != null) Gold else GoldDim, RoundedCornerShape(12.dp))
                .then(if (onClick != null) Modifier.clickable(enabled = enabled, role = Role.Checkbox, onClick = onClick) else Modifier)
                .semantics {
                    contentDescription = if (revealed) card.name else "Закрытая карта"
                    if (onClick != null) {
                        selected = selection != null
                        stateDescription = selection?.let { "Выбрана, позиция $it" } ?: "Не выбрана"
                    }
                },
            contentAlignment = Alignment.Center,
        ) {
            if (rotation > 90f) {
                SubcomposeAsyncImage(
                    model = card.imageUrl, contentDescription = null, contentScale = ContentScale.Fit,
                    modifier = Modifier.fillMaxSize().padding(4.dp).graphicsLayer { rotationY = 180f },
                    loading = { Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator(Modifier.size(24.dp), color = Gold) } },
                    error = { Box(Modifier.fillMaxSize().padding(8.dp), contentAlignment = Alignment.Center) { Text(card.name, textAlign = TextAlign.Center, style = MaterialTheme.typography.labelMedium) } },
                )
            } else {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("✦", style = MaterialTheme.typography.headlineLarge, color = Gold)
                    Text("tarot\nsphere", style = MaterialTheme.typography.labelMedium, textAlign = TextAlign.Center, color = Gold)
                }
            }
            if (selection != null && rotation > 90f) {
                Surface(Modifier.align(Alignment.TopEnd).padding(5.dp).graphicsLayer { rotationY = 180f }, color = Gold, shape = RoundedCornerShape(20.dp)) {
                    Text("$selection", Modifier.padding(horizontal = 8.dp, vertical = 3.dp), color = Night)
                }
            }
        }
    }
}
