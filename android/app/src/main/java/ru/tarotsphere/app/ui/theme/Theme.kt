package ru.tarotsphere.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val Scheme = darkColorScheme(
    primary = Gold,
    onPrimary = Ink,
    primaryContainer = GoldDim,
    onPrimaryContainer = Cream,
    secondary = Burgundy,
    onSecondary = Cream,
    background = Night,
    onBackground = Cream,
    surface = NightElevated,
    onSurface = Cream,
    surfaceVariant = NightCard,
    onSurfaceVariant = CreamMuted,
    outline = GoldDim,
    error = ErrorRose,
    onError = Cream,
)

@Composable
fun TarotSphereTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = Scheme,
        typography = Typography,
        content = content,
    )
}
