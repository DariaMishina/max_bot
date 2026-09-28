package ru.tarotsphere.app.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.foundation.text.KeyboardOptions
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
fun SphereLazyScreen(
    verticalArrangement: Arrangement.Vertical = Arrangement.spacedBy(WorkshopSpacing.item),
    content: LazyListScope.() -> Unit,
) {
    Box(
        Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).imePadding(),
        contentAlignment = Alignment.TopCenter,
    ) {
        LazyColumn(
            modifier = Modifier.widthIn(max = WorkshopSpacing.maxWidth).fillMaxSize(),
            contentPadding = PaddingValues(WorkshopSpacing.screen),
            verticalArrangement = verticalArrangement,
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
fun SectionHeading(title: String, subtitle: String? = null, modifier: Modifier = Modifier) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(title, Modifier.semantics { heading() }, style = MaterialTheme.typography.titleLarge)
        subtitle?.let {
            Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
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
fun QuestionField(
    value: String, onValueChange: (String) -> Unit, label: String, enabled: Boolean = true,
    minLines: Int = 3, maxLines: Int = 6, placeholder: String? = null, onImeDone: (() -> Unit)? = null,
) {
    OutlinedTextField(
        value = value, onValueChange = onValueChange, label = { Text(label) },
        placeholder = placeholder?.let { { Text(it) } },
        supportingText = if (value.length >= 800) ({ Text("${value.length}/1000", style = MaterialTheme.typography.bodySmall) }) else null,
        modifier = Modifier.fillMaxWidth(),
        enabled = enabled, minLines = minLines, maxLines = maxLines,
        keyboardOptions = KeyboardOptions(imeAction = if (onImeDone != null) ImeAction.Done else ImeAction.Default),
        keyboardActions = KeyboardActions(onDone = { onImeDone?.invoke() }),
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

@Composable
fun BalanceSummary(
    freeRemaining: Int,
    paidRemaining: Int,
    totalUsed: Int,
    unlimitedText: String? = null,
    offline: Boolean = false,
    onShop: () -> Unit,
    onRefresh: () -> Unit,
    actionsEnabled: Boolean = true,
) {
    val colors = MaterialTheme.colorScheme
    Surface(color = colors.secondaryContainer, shape = MaterialTheme.shapes.large) {
        Column(Modifier.fillMaxWidth().padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Ваш запас", style = MaterialTheme.typography.labelMedium, color = colors.secondary)
                Text(
                    if (unlimitedText != null) "Безлимит активен" else "Расклады на новые вопросы",
                    style = MaterialTheme.typography.titleLarge,
                    color = colors.onSecondaryContainer,
                )
                unlimitedText?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = colors.onSecondaryContainer) }
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                BalanceMetric("В подарок", freeRemaining.toString(), Modifier.weight(1f))
                BalanceMetric("Куплено", paidRemaining.toString(), Modifier.weight(1f))
            }
            Text("Всего сделано раскладов: $totalUsed", style = MaterialTheme.typography.bodySmall, color = colors.onSecondaryContainer)
            if (offline) Text(
                "Показан сохранённый баланс. Он обновится после подключения к интернету.",
                style = MaterialTheme.typography.bodySmall,
                color = colors.onSecondaryContainer,
            )
            PrimaryAction("Выбрать расклады", onShop, enabled = actionsEnabled)
            TextButton(onClick = onRefresh, enabled = actionsEnabled, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                Text("Обновить баланс")
            }
        }
    }
}

@Composable
private fun BalanceMetric(label: String, value: String, modifier: Modifier = Modifier) {
    val colors = MaterialTheme.colorScheme
    Surface(modifier, color = colors.surface.copy(alpha = 0.72f), shape = MaterialTheme.shapes.medium) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(value, style = MaterialTheme.typography.headlineMedium, color = colors.onSurface)
            Text(label, style = MaterialTheme.typography.bodySmall, color = colors.onSurfaceVariant)
        }
    }
}

@Composable
fun PackageCard(
    title: String,
    price: String,
    description: String? = null,
    action: String = "Выбрать",
    emphasized: Boolean = false,
    onChoose: () -> Unit,
) {
    val colors = MaterialTheme.colorScheme
    val container = if (emphasized) colors.primaryContainer else colors.surface
    val foreground = if (emphasized) colors.onPrimaryContainer else colors.onSurface
    Surface(
        color = container,
        contentColor = foreground,
        shape = MaterialTheme.shapes.large,
        border = BorderStroke(1.dp, if (emphasized) colors.primary.copy(alpha = 0.35f) else colors.outlineVariant),
    ) {
        Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.Top) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(title, style = MaterialTheme.typography.titleMedium)
                    description?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = foreground.copy(alpha = 0.76f)) }
                }
                Text(price, style = MaterialTheme.typography.titleLarge)
            }
            SecondaryAction(action, onChoose)
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
