package ru.tarotsphere.app.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import ru.tarotsphere.app.ui.theme.TarotSphereTheme

/** Shared controls, including disabled/error states, at small width and large font. */
@Preview(name = "Мастерская · 360", widthDp = 360, heightDp = 1000, showBackground = true)
@Preview(name = "Мастерская · 412", widthDp = 412, heightDp = 1000, showBackground = true)
@Preview(name = "Мастерская · шрифт 200%", widthDp = 360, heightDp = 1600, fontScale = 2f, showBackground = true)
@Composable
private fun WorkshopPreview() {
    TarotSphereTheme {
        SphereScreen {
            SphereHeader("О чём спросим карты?", "Место для вашего вопроса.", "Сфера Таро")
            QuestionField("Что поможет мне двигаться вперёд?", {}, "Ваш вопрос", minLines = 2)
            ChoiceOption("Довериться колоде", "Три случайные карты для вашего вопроса", true, {})
            ChoiceOption("Выбрать интуитивно", "Откройте три из девяти закрытых карт", false, {})
            PrimaryAction("Получить толкование", {})
            WorkshopDivider()
            Text("Решения остаются за вами.", style = MaterialTheme.typography.bodyLarge)
            PrimaryAction("Задать уточняющий вопрос", {}, olive = true)
            PrimaryAction("Готовим толкование…", {}, enabled = false)
            StatusPanel("Нет подключения", "Проверьте интернет и попробуйте ещё раз.", StatusTone.Error, {})
            PackageCard("Название пакета для проверки переноса", "1 500 ₽", "Описание условий покупки") {}
        }
    }
}
