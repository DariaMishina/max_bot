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
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.contentDescription
import kotlinx.coroutines.launch
import ru.tarotsphere.app.R
import ru.tarotsphere.app.ui.components.*
import ru.tarotsphere.app.ui.theme.TarotSphereTheme

private data class OnboardingPage(val title: String, val body: String)
private val Pages = listOf(
    OnboardingPage(
        "Место для вашего вопроса",
        "Выберите три карты и посмотрите на ситуацию с другой стороны. ИИ создаст толкование с учётом вашего вопроса.",
    ),
    OnboardingPage(
        "Ваш способ открыть карты",
        "Доверьтесь случайному выбору, откройте три карты интуитивно или укажите карты своей колоды. К готовому толкованию можно задать уточняющие вопросы.",
    ),
    OnboardingPage(
        "Три расклада в подарок",
        "Начните знакомство с трёх раскладов. Вопросы и толкования сохранятся в истории вашего аккаунта.\n\nПодарок доступен один раз на устройство. Его доступность проверяется при регистрации.",
    ),
)

@Composable
private fun OnboardingCards() {
    Box(Modifier.fillMaxWidth().height(250.dp).clearAndSetSemantics {}, contentAlignment = Alignment.Center) {
        listOf(-1, 1, 0).forEach { position ->
            TarotCardBack(Modifier.offset(x = (position * 58).dp, y = (if (position == 0) -5 else 8).dp)
                .size(width = 118.dp, height = 190.dp).graphicsLayer { rotationZ = position * 12f }
                .clip(RoundedCornerShape(12.dp)))
        }
    }
}

@Composable
fun OnboardingScreen(onFinished: () -> Unit) {
    val pagerState = rememberPagerState(pageCount = { Pages.size })
    val scope = rememberCoroutineScope()
    val last = pagerState.currentPage == Pages.lastIndex
    Box(Modifier.fillMaxSize().workshopPaper().statusBarsPadding().navigationBarsPadding(), contentAlignment = Alignment.TopCenter) {
        Column(Modifier.widthIn(max = WorkshopSpacing.maxWidth).fillMaxSize().padding(horizontal = 24.dp)) {
            Row(Modifier.fillMaxWidth().padding(top = 12.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                WorkshopBrand(Modifier.size(44.dp))
                Spacer(Modifier.width(8.dp))
                Text(stringResource(R.string.app_name), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
            }
            HorizontalPager(state = pagerState, modifier = Modifier.weight(1f).fillMaxWidth()) { index ->
                Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(vertical = 16.dp), verticalArrangement = Arrangement.Center) {
                    OnboardingCards()
                    Spacer(Modifier.height(24.dp))
                    WorkshopDivider()
                    Spacer(Modifier.height(20.dp))
                    Text(Pages[index].title, Modifier.fillMaxWidth(), style = MaterialTheme.typography.displaySmall,
                        textAlign = TextAlign.Center)
                    Spacer(Modifier.height(16.dp))
                    Text(Pages[index].body, Modifier.fillMaxWidth(), style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
                    Spacer(Modifier.height(24.dp))
                }
            }
            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(bottom = 12.dp)) {
                Row(Modifier.fillMaxWidth().semantics { contentDescription = "Страница ${pagerState.currentPage + 1} из ${Pages.size}" }, horizontalArrangement = Arrangement.Center) {
                    Pages.forEachIndexed { index, _ ->
                        Box(Modifier.padding(4.dp).size(if (index == pagerState.currentPage) 9.dp else 7.dp).clip(CircleShape)
                            .background(if (index == pagerState.currentPage) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant))
                    }
                }
                Spacer(Modifier.height(12.dp))
                PrimaryAction(if (last) "Продолжить" else "Дальше", onClick = {
                    if (last) onFinished() else scope.launch { pagerState.animateScrollToPage(pagerState.currentPage + 1) }
                })
                if (!last) TextButton(onClick = onFinished, modifier = Modifier.heightIn(min = 48.dp)) { Text("Пропустить") }
            }
        }
    }
}

@Preview(widthDp = 360, heightDp = 800, showBackground = true)
@Preview(name = "Крупный шрифт", widthDp = 360, heightDp = 800, fontScale = 2f, showBackground = true)
@Composable
private fun OnboardingPreview() { TarotSphereTheme { OnboardingScreen {} } }
