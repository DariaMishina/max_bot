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

@Composable
fun TarotCardBack(modifier: Modifier = Modifier) {
    Box(modifier.background(MaterialTheme.colorScheme.secondaryContainer).padding(7.dp)
        .border(1.dp, MaterialTheme.colorScheme.secondary.copy(alpha = 0.5f), RoundedCornerShape(8.dp)), contentAlignment = Alignment.Center) {
        SphereEmblem(Modifier.fillMaxWidth(0.82f).aspectRatio(1f), color = MaterialTheme.colorScheme.secondary)
    }
}

@Composable
fun TarotCardView(
    card: TarotCard, revealed: Boolean, modifier: Modifier = Modifier,
    selection: Int? = null, onClick: (() -> Unit)? = null, enabled: Boolean = true,
) {
    val rotation by animateFloatAsState(if (revealed) 180f else 0f, tween(400), label = "cardFlip")
    val colors = MaterialTheme.colorScheme
    // Semantics and selection badge stay outside the rotating artwork.
    Box(
        modifier.fillMaxWidth().aspectRatio(0.62f)
            .then(if (onClick != null) Modifier.clickable(enabled = enabled, role = Role.Checkbox, onClick = onClick) else Modifier)
            .semantics(mergeDescendants = true) {
                contentDescription = if (revealed) card.name else "Закрытая карта"
                if (onClick != null) {
                    selected = selection != null
                    stateDescription = selection?.let { "Выбрана, позиция $it" } ?: "Не выбрана"
                }
            },
    ) {
        Box(Modifier.fillMaxSize().graphicsLayer { rotationY = rotation; cameraDistance = 12 * density }
            .clip(RoundedCornerShape(12.dp)).background(colors.surface)
            .border(if (selection != null) 2.dp else 1.dp, if (selection != null) colors.primary else colors.outlineVariant, RoundedCornerShape(12.dp))) {
            if (rotation > 90f) {
                SubcomposeAsyncImage(
                    model = card.imageUrl, contentDescription = null, contentScale = ContentScale.Fit,
                    modifier = Modifier.fillMaxSize().padding(4.dp).graphicsLayer { rotationY = 180f },
                    loading = { Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator(Modifier.size(24.dp)) } },
                    error = { Box(Modifier.fillMaxSize().padding(8.dp), contentAlignment = Alignment.Center) { Text(card.name, textAlign = TextAlign.Center, style = MaterialTheme.typography.labelMedium) } },
                )
            } else TarotCardBack(Modifier.fillMaxSize())
        }
        if (selection != null) {
            Surface(Modifier.align(Alignment.TopStart).padding(5.dp).clearAndSetSemantics {}, color = colors.primary, shape = RoundedCornerShape(12.dp)) {
                Text("$selection", Modifier.padding(horizontal = 8.dp, vertical = 3.dp), color = colors.onPrimary, style = MaterialTheme.typography.labelMedium)
            }
        }
    }
}
