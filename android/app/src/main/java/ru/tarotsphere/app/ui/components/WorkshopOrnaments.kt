package ru.tarotsphere.app.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.dp
import ru.tarotsphere.app.R

/** Lightweight botanical linework, kept outside text and touch targets. */
@Composable
fun WorkshopBranch(modifier: Modifier = Modifier) {
    val olive = MaterialTheme.colorScheme.secondary
    Canvas(modifier.clearAndSetSemantics {}) {
        scale(size.width / 120f, size.height / 64f, pivot = Offset.Zero) {
            val stem = Path().apply {
                moveTo(4f, 60f)
                cubicTo(35f, 57f, 57f, 17f, 112f, 8f)
            }
            drawPath(stem, olive.copy(alpha = 0.65f), style = Stroke(1f))
            listOf(25f to 50f, 46f to 35f, 67f to 22f, 88f to 13f).forEach { (x, y) ->
                val upper = Path().apply {
                    moveTo(x, y)
                    cubicTo(x - 16f, y - 3f, x - 15f, y - 16f, x - 14f, y - 22f)
                    cubicTo(x - 2f, y - 18f, x + 2f, y - 7f, x, y)
                }
                val lower = Path().apply {
                    moveTo(x, y)
                    cubicTo(x + 5f, y + 13f, x + 18f, y + 12f, x + 23f, y + 8f)
                    cubicTo(x + 17f, y, x + 7f, y - 2f, x, y)
                }
                drawPath(upper, olive.copy(alpha = 0.19f))
                drawPath(lower, olive.copy(alpha = 0.15f))
                drawPath(upper, olive.copy(alpha = 0.45f), style = Stroke(0.7f))
                drawPath(lower, olive.copy(alpha = 0.45f), style = Stroke(0.7f))
            }
        }
    }
}

@Composable
fun WorkshopBrand(modifier: Modifier = Modifier) {
    Image(painterResource(R.drawable.sphere_mark), contentDescription = null,
        modifier = modifier.clearAndSetSemantics {})
}

@Composable
fun WorkshopDivider(modifier: Modifier = Modifier) {
    val line = MaterialTheme.colorScheme.outlineVariant
    Row(modifier.fillMaxWidth().clearAndSetSemantics {}, verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        androidx.compose.material3.HorizontalDivider(Modifier.weight(1f), color = line)
        SphereEmblem(Modifier.size(24.dp), MaterialTheme.colorScheme.tertiary)
        androidx.compose.material3.HorizontalDivider(Modifier.weight(1f), color = line)
    }
}
