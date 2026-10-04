package ru.tarotsphere.app.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import ru.tarotsphere.app.domain.validation.isMeaningfulQuestion
import ru.tarotsphere.app.domain.validation.normalizeQuestion

class QuestionValidationTest {
    @Test fun rejectsSymbolsNumbersAndRepeatedNoise() {
        listOf("", "   ", "!", "???", "🔮", "123", "а", "аааа", "xxx", "\u200b!").forEach {
            assertFalse(it, isMeaningfulQuestion(it))
        }
    }

    @Test fun acceptsQuestionsAndShortTopics() {
        listOf("Работа", "Любовь?", "Что дальше?", "Стоит ли менять работу").forEach {
            assertTrue(it, isMeaningfulQuestion(it))
        }
    }

    @Test fun normalizesWhitespaceAndInvisibleCharacters() {
        assertEquals("Что дальше?", normalizeQuestion("  Что\n\u200b дальше?  "))
    }
}
