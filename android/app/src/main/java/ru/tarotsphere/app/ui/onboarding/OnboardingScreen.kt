package ru.tarotsphere.app.ui.onboarding

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import ru.tarotsphere.app.R
import ru.tarotsphere.app.ui.components.*
import ru.tarotsphere.app.ui.theme.TarotSphereTheme

private data class OnboardingPage(val title: String, val body: String)
private val Pages = listOf(
    OnboardingPage("Место для вашего вопроса", "Выберите три карты и посмотрите на ситуацию с другой стороны. Начать можно без регистрации."),
    OnboardingPage("Три расклада в подарок", "Задайте первый вопрос бесплатно. Готовые расклады сохранятся в истории. Доступ к ним привязан к этому телефону."),
    OnboardingPage("Доверьтесь своему выбору", "Откройте три карты из девяти или позвольте колоде выбрать за вас. После толкования можно задать уточнения."),
)

@Composable
private fun OnboardingCards() {
    Box(Modifier.fillMaxWidth().height(196.dp).clearAndSetSemantics {}, contentAlignment = Alignment.Center) {
        listOf(-1, 1, 0).forEach { position ->
            TarotCardBack(Modifier.offset(x = (position * 58).dp, y = (if (position == 0) -5 else 8).dp)
                .size(width = 98.dp, height = 158.dp).graphicsLayer { rotationZ = position * 12f }
                .clip(RoundedCornerShape(12.dp)))
        }
    }
}

@Composable
fun OnboardingScreen(onFinished: () -> Unit) {
    val pagerState = rememberPagerState(pageCount = { Pages.size })
    val scope = rememberCoroutineScope()
    val last = pagerState.currentPage == Pages.lastIndex
    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).statusBarsPadding().navigationBarsPadding(), contentAlignment = Alignment.TopCenter) {
        Column(Modifier.widthIn(max = WorkshopSpacing.maxWidth).fillMaxSize().padding(horizontal = 24.dp)) {
            Row(Modifier.fillMaxWidth().padding(top = 12.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                SphereEmblem(Modifier.size(32.dp))
                Spacer(Modifier.width(8.dp))
                Text(stringResource(R.string.app_name), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
            }
            HorizontalPager(state = pagerState, modifier = Modifier.weight(1f).fillMaxWidth()) { index ->
                Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(vertical = 16.dp), verticalArrangement = Arrangement.Center) {
                    OnboardingCards()
                    Spacer(Modifier.height(24.dp))
                    SphereHeader(Pages[index].title, Pages[index].body)
                    Spacer(Modifier.height(24.dp))
                }
            }
            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(bottom = 12.dp)) {
                Row(Modifier.fillMaxWidth().clearAndSetSemantics {}, horizontalArrangement = Arrangement.Center) {
                    Pages.forEachIndexed { index, _ ->
                        Box(Modifier.padding(4.dp).size(if (index == pagerState.currentPage) 9.dp else 7.dp).clip(CircleShape)
                            .background(if (index == pagerState.currentPage) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant))
                    }
                }
                Spacer(Modifier.height(12.dp))
                PrimaryAction(if (last) "Сделать первый расклад" else "Дальше", onClick = {
                    if (last) onFinished() else scope.launch { pagerState.animateScrollToPage(pagerState.currentPage + 1) }
                })
                if (!last) TextButton(onClick = onFinished, modifier = Modifier.heightIn(min = 48.dp)) { Text("Пропустить") }
                else Text("Регистрация не нужна", Modifier.fillMaxWidth().padding(top = 12.dp), textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Preview(widthDp = 360, heightDp = 800, showBackground = true)
@Preview(name = "Крупный шрифт", widthDp = 360, heightDp = 800, fontScale = 2f, showBackground = true)
@Composable
private fun OnboardingPreview() { TarotSphereTheme { OnboardingScreen {} } }
