package ru.tarotsphere.app.ui.onboarding

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import ru.tarotsphere.app.ui.components.DeckCard
import ru.tarotsphere.app.ui.theme.CreamMuted
import ru.tarotsphere.app.ui.theme.Gold
import ru.tarotsphere.app.ui.theme.Ink
import ru.tarotsphere.app.ui.theme.Night

private data class OnboardingPage(
    val title: String,
    val body: String,
)

private val Pages = listOf(
    OnboardingPage(
        title = "Таро на этом телефоне",
        body = "Задайте вопрос, выберите три карты или доверьте колоде. Толкование приходит с сервера — без чата и без входа.",
    ),
    OnboardingPage(
        title = "Три расклада бесплатно",
        body = "Сразу после старта у вас есть 3 бесплатных расклада. Покупки и история живут на этом устройстве, пока нет входов.",
    ),
    OnboardingPage(
        title = "Как выбрать карты",
        body = "Либо карты выпадут сами, либо вы откроете девять рубашек и возьмёте три. Полный экран расклада появится на следующем этапе.",
    ),
)

@Composable
fun OnboardingScreen(onFinished: () -> Unit) {
    val pagerState = rememberPagerState(pageCount = { Pages.size })
    val scope = rememberCoroutineScope()
    val last = pagerState.currentPage == Pages.lastIndex

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Night)
            .statusBarsPadding()
            .navigationBarsPadding()
            .padding(24.dp),
        verticalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(
            text = "tarot sphere",
            style = MaterialTheme.typography.labelLarge,
            color = Gold,
        )
        HorizontalPager(
            state = pagerState,
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
        ) { index ->
            val page = Pages[index]
            Column(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.Center,
            ) {
                DeckCard {
                    Text(page.title, style = MaterialTheme.typography.headlineMedium)
                    Spacer(Modifier.height(12.dp))
                    Text(
                        page.body,
                        style = MaterialTheme.typography.bodyLarge,
                        color = CreamMuted,
                    )
                }
            }
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Row(
                horizontalArrangement = Arrangement.Center,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Pages.forEachIndexed { index, _ ->
                    val selected = index == pagerState.currentPage
                    Box(
                        modifier = Modifier
                            .padding(4.dp)
                            .size(if (selected) 10.dp else 8.dp)
                            .clip(CircleShape)
                            .background(if (selected) Gold else CreamMuted.copy(alpha = 0.35f)),
                    )
                }
            }
            Spacer(Modifier.height(16.dp))
            Button(
                onClick = {
                    if (last) {
                        onFinished()
                    } else {
                        scope.launch { pagerState.animateScrollToPage(pagerState.currentPage + 1) }
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Gold, contentColor = Ink),
                shape = RoundedCornerShape(16.dp),
            ) {
                Text(if (last) "Начать" else "Дальше")
            }
            if (!last) {
                TextButton(onClick = onFinished) {
                    Text("Пропустить", color = CreamMuted)
                }
            } else {
                Spacer(Modifier.height(12.dp))
                Text(
                    "Регистрация не нужна",
                    style = MaterialTheme.typography.bodyMedium,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.width(280.dp),
                )
            }
        }
    }
}
