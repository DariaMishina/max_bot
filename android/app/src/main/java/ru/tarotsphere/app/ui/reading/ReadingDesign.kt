package ru.tarotsphere.app.ui.reading

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.tarotsphere.app.ui.components.BotanicalBackdrop
import ru.tarotsphere.app.ui.components.WorkshopDivider
import ru.tarotsphere.app.ui.components.WorkshopSheet
import ru.tarotsphere.app.ui.theme.InkWine
import ru.tarotsphere.app.ui.theme.WorkshopSerif

internal val ReadingSerif = WorkshopSerif
internal val ReadingWine = InkWine

@Composable
internal fun ReadingPage(content: @Composable ColumnScope.() -> Unit) {
    BotanicalBackdrop {
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
    WorkshopDivider(modifier)
}

@Composable
internal fun ReadingPaper(olive: Boolean = false, content: @Composable ColumnScope.() -> Unit) {
    WorkshopSheet(olive = olive, content = content)
}

@Composable
internal fun ReadingSectionTitle(text: String) {
    Text(text, Modifier.fillMaxWidth().semantics { heading() }, fontFamily = ReadingSerif,
        fontWeight = FontWeight.SemiBold, fontSize = 30.sp, lineHeight = 34.sp,
        textAlign = TextAlign.Center, color = ReadingWine)
}
