package ru.tarotsphere.app.ui.reading

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.ImageShader
import androidx.compose.ui.graphics.ShaderBrush
import androidx.compose.ui.graphics.TileMode
import androidx.compose.ui.res.imageResource
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.ExperimentalTextApi
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.tarotsphere.app.R
import ru.tarotsphere.app.ui.components.SphereEmblem

// Deliberately scoped to the reading screen until the owner accepts this visual direction.
@OptIn(ExperimentalTextApi::class)
internal val ReadingSerif = FontFamily(
    Font(R.font.cormorant_garamond, weight = FontWeight.Normal, variationSettings = FontVariation.Settings(FontVariation.weight(400))),
    Font(R.font.cormorant_garamond, weight = FontWeight.Medium, variationSettings = FontVariation.Settings(FontVariation.weight(500))),
    Font(R.font.cormorant_garamond, weight = FontWeight.SemiBold, variationSettings = FontVariation.Settings(FontVariation.weight(600))),
    Font(R.font.cormorant_garamond, weight = FontWeight.Bold, variationSettings = FontVariation.Settings(FontVariation.weight(700))),
)
internal val ReadingWine = Color(0xFF581D2B)
private val ReadingGold = Color(0xFFB18C54)

@Composable
internal fun ReadingPage(content: @Composable ColumnScope.() -> Unit) {
    Box(Modifier.fillMaxSize().background(Color(0xFFF6EFDF)).imePadding(), contentAlignment = Alignment.TopCenter) {
        // Fixed decorative paper never stretches with the length of an interpretation.
        Image(painterResource(R.drawable.reading_botanical_paper), contentDescription = null,
            contentScale = ContentScale.FillBounds, modifier = Modifier.matchParentSize())
        Column(
            Modifier.widthIn(max = 600.dp).fillMaxWidth().fillMaxHeight()
                .verticalScroll(rememberScrollState()).padding(horizontal = 16.dp).padding(bottom = 28.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp), content = content,
        )
    }
}

@Composable
internal fun ReadingHero() {
    Column(Modifier.fillMaxWidth().padding(horizontal = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("СФЕРА ТАРО", letterSpacing = 2.sp, style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.secondary, textAlign = TextAlign.Center)
        Text("Ваше толкование", modifier = Modifier.fillMaxWidth().semantics { heading() },
            fontFamily = ReadingSerif, fontWeight = FontWeight.Bold, fontSize = 44.sp, lineHeight = 44.sp, letterSpacing = (-.6).sp,
            color = ReadingWine, textAlign = TextAlign.Center)
        Text("Три карты для вашего вопроса", fontFamily = ReadingSerif, fontWeight = FontWeight.Medium,
            fontSize = 22.sp, lineHeight = 26.sp, textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.secondary)
        ReadingRule(Modifier.padding(horizontal = 32.dp))
    }
}

@Composable
internal fun ReadingRule(modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        HorizontalDivider(Modifier.weight(1f), thickness = .7.dp, color = ReadingGold.copy(alpha = .65f))
        SphereEmblem(Modifier.size(24.dp), ReadingGold)
        HorizontalDivider(Modifier.weight(1f), thickness = .7.dp, color = ReadingGold.copy(alpha = .65f))
    }
}

@Composable
internal fun ReadingPaper(olive: Boolean = false, content: @Composable ColumnScope.() -> Unit) {
    val shape = RoundedCornerShape(28.dp)
    val base = if (olive) Color(0xFFE9ECD9) else Color(0xFFFFF9EE)
    val texture = ImageBitmap.imageResource(R.drawable.reading_paper_texture)
    val paper = remember(texture) { ShaderBrush(ImageShader(texture, TileMode.Repeated, TileMode.Repeated)) }
    Box(Modifier.fillMaxWidth().shadow(5.dp, shape, ambientColor = Color(0xFF6C4B23), spotColor = Color(0xFF6C4B23))
        .clip(shape).background(base).background(paper, alpha = if (olive) .32f else .65f)
        .border(1.dp, ReadingGold.copy(alpha = .65f), shape).padding(5.dp)
        .border(.5.dp, ReadingGold.copy(alpha = .25f), RoundedCornerShape(23.dp))) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 13.dp, vertical = 18.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp), content = content)
    }
}

@Composable
internal fun ReadingSectionTitle(text: String) {
    Text(text, Modifier.fillMaxWidth().semantics { heading() }, fontFamily = ReadingSerif,
        fontWeight = FontWeight.SemiBold, fontSize = 30.sp, lineHeight = 34.sp,
        textAlign = TextAlign.Center, color = ReadingWine)
}
