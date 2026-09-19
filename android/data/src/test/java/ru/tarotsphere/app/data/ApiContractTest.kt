package ru.tarotsphere.app.data

import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test
import ru.tarotsphere.app.data.api.dto.*

class ApiContractTest {
    private val json = Json { ignoreUnknownKeys = true }
    @Test fun createAndDetailUseDifferentIdFields() {
        val common = """"question":"Q","cards":[{"id":"00-TheFool","name":"Шут","image_url":"http://internal:8083/static/images/00-TheFool.png"}],"interpretation":"Text","is_free":true,"follow_ups_remaining":2"""
        val created = json.decodeFromString<ReadingDto>("{" + "\"divination_id\":42," + common + "}").toDomain()
        val detail = json.decodeFromString<ReadingDto>("{" + "\"id\":42," + common + "}").toDomain()
        assertEquals(42L, created.id)
        assertEquals(created, detail)
        assertTrue(created.cards.single().imageUrl.startsWith("https://"))
        assertFalse(created.cards.single().imageUrl.contains("internal"))
    }
    @Test fun historyCursorAndFollowUpTranscriptAreDecoded() {
        val page = json.decodeFromString<HistoryResponseDto>("""{"items":[],"next_before_id":123}""")
        assertEquals(123L, page.nextBeforeId)
        val result = json.decodeFromString<FollowUpsDto>("""{"follow_ups":[{"request_id":"ignored","question":"Q","answer":"A"}],"follow_ups_remaining":0}""")
        assertEquals("A", result.followUps.single().answer)
        assertEquals(0, result.remaining)
    }
    @Test fun catalogHasConsultationsAndContact() {
        val catalog = json.decodeFromString<CatalogDto>("""{"packages":[],"consultations":[{"id":"basic","name":"Базовая","price_rub":500}],"payment_methods":["rustore","yookassa"],"tarologist_url":"https://example.test/contact"}""").toDomain()
        assertEquals(500, catalog.consultations.single().priceRub)
        assertEquals(2, catalog.paymentMethods.size)
    }
}
