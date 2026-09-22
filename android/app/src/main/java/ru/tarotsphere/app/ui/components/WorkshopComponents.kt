package ru.tarotsphere.app.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp

object WorkshopSpacing {
    val screen = 20.dp
    val section = 24.dp
    val item = 12.dp
    val maxWidth = 600.dp
}

@Composable
fun SphereScreen(content: @Composable ColumnScope.() -> Unit) {
    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).imePadding(), contentAlignment = Alignment.TopCenter) {
        Column(
            Modifier.widthIn(max = WorkshopSpacing.maxWidth).fillMaxWidth().fillMaxHeight()
                .verticalScroll(rememberScrollState()).padding(WorkshopSpacing.screen),
            verticalArrangement = Arrangement.spacedBy(WorkshopSpacing.section),
            content = content,
        )
    }
}

@Composable
fun SphereHeader(title: String, subtitle: String? = null, eyebrow: String? = null) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        eyebrow?.let { Text(it, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.secondary) }
        Text(title, Modifier.semantics { heading() }, style = MaterialTheme.typography.headlineMedium)
        subtitle?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
}

@Composable
fun PrimaryAction(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    Button(
        onClick = onClick, enabled = enabled,
        modifier = modifier.fillMaxWidth().heightIn(min = 56.dp), shape = MaterialTheme.shapes.medium,
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 14.dp),
        colors = ButtonDefaults.buttonColors(
            disabledContainerColor = MaterialTheme.colorScheme.surfaceVariant,
            disabledContentColor = MaterialTheme.colorScheme.onSurfaceVariant,
        ),
    ) { Text(text) }
}

@Composable
fun SecondaryAction(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    OutlinedButton(onClick, modifier.fillMaxWidth().heightIn(min = 48.dp), enabled = enabled,
        shape = MaterialTheme.shapes.medium, contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp)) { Text(text) }
}

@Composable
fun ChoiceOption(title: String, description: String, selected: Boolean, onClick: () -> Unit, enabled: Boolean = true) {
    val colors = MaterialTheme.colorScheme
    Surface(
        modifier = Modifier.fillMaxWidth().selectable(selected = selected, enabled = enabled, role = Role.RadioButton, onClick = onClick),
        color = if (selected) colors.primaryContainer else colors.surface,
        shape = MaterialTheme.shapes.medium,
        border = BorderStroke(if (selected) 1.5.dp else 1.dp, if (selected) colors.primary else colors.outlineVariant),
    ) {
        Row(Modifier.heightIn(min = 72.dp).padding(horizontal = 12.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            RadioButton(selected = selected, onClick = null, enabled = enabled)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium, color = if (enabled) colors.onSurface else colors.onSurfaceVariant)
                Text(description, style = MaterialTheme.typography.bodyMedium, color = colors.onSurfaceVariant)
            }
        }
    }
}

@Composable
fun QuestionField(value: String, onValueChange: (String) -> Unit, label: String, enabled: Boolean = true, minLines: Int = 3, placeholder: String? = null) {
    OutlinedTextField(
        value = value, onValueChange = onValueChange, label = { Text(label) },
        placeholder = placeholder?.let { { Text(it) } },
        supportingText = { Text("${value.length}/1000", style = MaterialTheme.typography.bodySmall) },
        modifier = Modifier.fillMaxWidth(), enabled = enabled, minLines = minLines, maxLines = 6,
        shape = MaterialTheme.shapes.medium,
        colors = OutlinedTextFieldDefaults.colors(
            focusedContainerColor = MaterialTheme.colorScheme.surface,
            unfocusedContainerColor = MaterialTheme.colorScheme.surface,
            disabledContainerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
    )
}

enum class StatusTone { Info, Error, Progress }

@Composable
fun StatusPanel(title: String, body: String? = null, tone: StatusTone = StatusTone.Info, onRetry: (() -> Unit)? = null) {
    val colors = MaterialTheme.colorScheme
    Surface(color = if (tone == StatusTone.Error) colors.errorContainer else colors.secondaryContainer, shape = MaterialTheme.shapes.medium) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (tone == StatusTone.Progress) LinearProgressIndicator(Modifier.fillMaxWidth(), color = colors.secondary)
            val foreground = if (tone == StatusTone.Error) colors.onErrorContainer else colors.onSecondaryContainer
            Text(title, style = MaterialTheme.typography.titleMedium, color = foreground)
            body?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = foreground) }
            if (onRetry != null) TextButton(onClick = onRetry) { Text("Повторить") }
        }
    }
}

/** Decorative, code-native mark: no bitmap or remote request is needed for a card back. */
@Composable
fun SphereEmblem(modifier: Modifier = Modifier, color: Color = MaterialTheme.colorScheme.primary) {
    Canvas(modifier) {
        val diameter = size.minDimension * 0.68f
        val radius = diameter / 2f
        val stroke = Stroke(width = 1.4.dp.toPx())
        drawCircle(color, radius, center, style = stroke)
        drawOval(color.copy(alpha = 0.65f), topLeft = Offset(center.x - radius * 0.42f, center.y - radius), size = Size(radius * 0.84f, diameter), style = stroke)
        drawLine(color, Offset(center.x - radius, center.y), Offset(center.x + radius, center.y), strokeWidth = 1.dp.toPx())
        drawCircle(color, 3.dp.toPx(), Offset(center.x + radius * 0.82f, center.y - radius * 0.55f))
    }
}
