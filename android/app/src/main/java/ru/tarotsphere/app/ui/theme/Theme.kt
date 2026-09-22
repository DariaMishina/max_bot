package ru.tarotsphere.app.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

private val Scheme = lightColorScheme(
    primary = Wine, onPrimary = PaperSurface,
    primaryContainer = WineSoft, onPrimaryContainer = Wine,
    secondary = Olive, onSecondary = PaperSurface,
    secondaryContainer = OliveSoft, onSecondaryContainer = Color(0xFF303D28),
    tertiary = Wine, onTertiary = PaperSurface,
    background = Paper, onBackground = WorkshopInk,
    surface = PaperSurface, onSurface = WorkshopInk,
    surfaceVariant = PaperInset, onSurfaceVariant = WorkshopMuted,
    surfaceContainerLowest = PaperSurface, surfaceContainerLow = PaperSurface,
    surfaceContainer = PaperInset, surfaceContainerHigh = Color(0xFFE9E0D5),
    surfaceContainerHighest = Color(0xFFE2D8CD),
    outline = PaperOutline, outlineVariant = PaperDivider,
    error = WorkshopError, onError = PaperSurface,
    errorContainer = Color(0xFFF8E1DF), onErrorContainer = Color(0xFF72212B),
    inverseSurface = WorkshopInk, inverseOnSurface = Paper,
    inversePrimary = Color(0xFFE9B4C7), surfaceTint = Wine,
)

@Composable
fun TarotSphereTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = Scheme,
        typography = Typography,
        shapes = Shapes(
            extraSmall = RoundedCornerShape(8.dp), small = RoundedCornerShape(12.dp),
            medium = RoundedCornerShape(16.dp), large = RoundedCornerShape(24.dp), extraLarge = RoundedCornerShape(28.dp),
        ),
        content = content,
    )
}
