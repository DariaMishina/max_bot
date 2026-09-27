package ru.tarotsphere.app.ui.reading

import androidx.compose.ui.text.font.FontWeight
import org.junit.Assert.assertEquals
import org.junit.Test

class ReadingFormattingTest {
    @Test
    fun sectionHeadingsAreBoldWithoutBoldingTheirParagraphs() {
        val text = """Прошлое: Первый абзац.

Настоящее — Второй абзац.

Будущее: Третий абзац.

Общее толкование: Итоговый абзац."""

        val formatted = emphasizeReadingSections(text)
        val boldParts = formatted.spanStyles
            .filter { it.item.fontWeight == FontWeight.Bold }
            .map { formatted.text.substring(it.start, it.end) }

        assertEquals(
            listOf("Прошлое:", "Настоящее —", "Будущее:", "Общее толкование:"),
            boldParts,
        )
    }
}
