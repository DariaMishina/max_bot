package ru.tarotsphere.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.SystemBarStyle
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.tarotsphere.app.domain.model.*
import ru.tarotsphere.app.ui.reading.ReadingContent
import ru.tarotsphere.app.ui.reading.ReadingUiState
import ru.tarotsphere.app.ui.theme.TarotSphereTheme

/** Offline fixture for visual QA. Debug source set only; never reads or writes an account. */
class ReadingReviewActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(statusBarStyle = SystemBarStyle.light(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT))
        val longText = intent.getBooleanExtra("long_text", false)
        val reading = Reading(
            id = -1,
            question = if (longText) "Как найти баланс между заботой о близких, профессиональными планами и собственным желанием начать новое дело, если времени на всё не хватает?"
                else "Что поможет мне двигаться вперёд?",
            cards = listOf(
                TarotCard("sun", "Солнце", "file:///android_asset/reading-review/sun.png"),
                TarotCard("moon", "Луна", "file:///android_asset/reading-review/moon.png"),
                TarotCard("star", "Звезда", "file:///android_asset/reading-review/star.png"),
            ),
            interpretation = "Прошлое: Солнце напоминает о том, что уже давало вам силы. Вспомните моменты ясности и уверенности — этот опыт остаётся с вами.\n\n" +
                "Настоящее: Луна предлагает не торопиться с выводами. Прислушайтесь к себе и отделите реальные обстоятельства от тревожных ожиданий.\n\n" +
                "Будущее: Звезда — повод заметить направление, которое вдохновляет. Небольшой, посильный шаг поможет вернуть ощущение движения." +
                if (longText) "\n\nОбщее толкование: Позвольте себе выбрать собственный темп. ".repeat(16) else "",
            isFree = true, createdAt = "2026-10-31", followUps = listOf(
                FollowUp("Как сделать первый шаг?", "Выберите небольшое действие, которое зависит от вас. Подумайте, что можно попробовать уже сегодня, не требуя от себя идеального результата.")),
            followUpsRemaining = 1,
        )
        setContent {
            TarotSphereTheme {
                var question by remember { mutableStateOf("") }
                var sent by remember { mutableStateOf(false) }
                Scaffold(bottomBar = {
                    Surface(color = MaterialTheme.colorScheme.surface) {
                        Text("Демо · проверка дизайна", Modifier.navigationBarsPadding().fillMaxWidth().padding(16.dp),
                            style = MaterialTheme.typography.labelMedium)
                    }
                }) { padding ->
                    Box(Modifier.padding(padding)) {
                        ReadingContent(ReadingUiState(reading = reading, question = question,
                            followUpError = if (sent) "Это демонстрация оформления. Запросы не отправляются." else null),
                            onBack = { finish() }, onNew = { finish() }, onShop = { finish() }, onRefresh = {},
                            onQuestion = { question = it }, onSend = { sent = true })
                    }
                }
            }
        }
    }
}
