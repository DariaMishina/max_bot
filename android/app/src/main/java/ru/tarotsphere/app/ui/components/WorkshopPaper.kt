package ru.tarotsphere.app.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawWithCache
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PointMode
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlin.random.Random

/** Seeded, cached paper grain: no image download, bitmap allocation or moving noise. */
fun Modifier.workshopPaper(): Modifier = drawWithCache {
    val random = Random(41)
    val grain = List((size.width * size.height / 220f).toInt().coerceAtMost(14000)) {
        Offset(random.nextFloat() * size.width, random.nextFloat() * size.height)
    }
    onDrawBehind {
        drawRect(Color(0xFFF6EFDF))
        drawPoints(grain, PointMode.Points, Color(0xFF98764D).copy(alpha = 0.065f), strokeWidth = 1.dp.toPx())
    }
}

/** A reusable native paper sheet. Content grows with font size and never overlaps ornament. */
@Composable
fun WorkshopSheet(modifier: Modifier = Modifier, olive: Boolean = false, content: @Composable ColumnScope.() -> Unit) {
    val colors = MaterialTheme.colorScheme
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(26.dp),
        color = if (olive) colors.secondaryContainer else colors.surface,
        border = BorderStroke(1.dp, if (olive) colors.secondary.copy(alpha = 0.35f) else colors.tertiary.copy(alpha = 0.35f)),
        shadowElevation = 2.dp,
    ) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(16.dp), content = content)
    }
}

@Composable
fun WorkshopStep(number: String, title: String, description: String? = null) {
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.Top) {
        Surface(color = MaterialTheme.colorScheme.secondaryContainer, shape = RoundedCornerShape(12.dp)) {
            Text(number, Modifier.padding(horizontal = 10.dp, vertical = 7.dp),
                style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.secondary)
        }
        SectionHeading(title, description, Modifier.weight(1f))
    }
}

@Composable
fun SelectionProgress(count: Int) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("Выбрано $count из 3", Modifier.fillMaxWidth(), textAlign = TextAlign.Center,
            style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.primary)
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            listOf("Прошлое", "Настоящее", "Будущее").forEachIndexed { index, label ->
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    LinearProgressIndicator(progress = { if (index < count) 1f else 0f },
                        modifier = Modifier.fillMaxWidth().clearAndSetSemantics {},
                        color = MaterialTheme.colorScheme.primary, trackColor = MaterialTheme.colorScheme.surfaceVariant)
                    Text(label, Modifier.fillMaxWidth(), textAlign = TextAlign.Center,
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

/** Botanical wreath shares its geometry across card backs and onboarding. */
@Composable
fun WorkshopWreath(modifier: Modifier = Modifier) {
    val olive = MaterialTheme.colorScheme.secondary
    val gold = MaterialTheme.colorScheme.tertiary
    androidx.compose.foundation.Canvas(modifier.clearAndSetSemantics {}) {
        fun point(x: Float, y: Float) = Offset(x * size.width, y * size.height)
        for (side in listOf(-1f, 1f)) {
            val stem = Path().apply {
                moveTo(size.width * .5f, size.height * .9f)
                cubicTo(size.width * (.5f + side * .44f), size.height * .73f,
                    size.width * (.5f + side * .42f), size.height * .3f,
                    size.width * (.5f + side * .19f), size.height * .08f)
            }
            drawPath(stem, gold.copy(alpha = .7f), style = Stroke(1.dp.toPx()))
            for (i in 0..6) {
                val y = .8f - i * .1f
                val x = .5f + side * (.18f + .13f * kotlin.math.sin(i / 6f * Math.PI).toFloat())
                for (direction in listOf(-1f, 1f)) {
                    val root = point(x, y)
                    val tip = point(x + side * direction * .12f, y - .13f)
                    val leaf = Path().apply {
                        moveTo(root.x, root.y)
                        quadraticTo(root.x + size.width * side * direction * .15f, root.y - size.height * .02f, tip.x, tip.y)
                        quadraticTo(root.x - size.width * side * direction * .025f, root.y - size.height * .08f, root.x, root.y)
                    }
                    drawPath(leaf, olive.copy(alpha = .5f))
                    drawPath(leaf, olive.copy(alpha = .8f), style = Stroke(.5.dp.toPx()))
                    drawLine(gold.copy(alpha = .65f), root, tip, .5.dp.toPx())
                }
            }
        }
    }
}
