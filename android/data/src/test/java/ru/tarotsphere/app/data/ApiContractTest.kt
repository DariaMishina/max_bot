package ru.tarotsphere.app.data

import kotlinx.serialization.json.Json
import kotlinx.serialization.encodeToString
import org.junit.Assert.*
import org.junit.Test
import ru.tarotsphere.app.data.api.dto.*

class ApiContractTest {
    private val json = Json { ignoreUnknownKeys = true }
    @Test fun balanceWorksWithOldAndNewServers() {
        assertNull(json.decodeFromString<BalanceDto>("{}").toDomain().trialStatus)
        val balance = json.decodeFromString<BalanceDto>("""{"trial_status":"device_used","paid_divinations_remaining":2}""").toDomain()
        assertEquals("device_used", balance.trialStatus)
        assertTrue(balance.canDivinate)
    }
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
    @Test fun appOpenPayloadContainsOnlyExpectedDiagnostics() {
        val payload = json.encodeToString(
            AppOpenRequestDto(
                installId = "123e4567-e89b-12d3-a456-426614174000",
                versionName = "0.8.1",
                versionCode = 7,
                channel = "alpha",
            ),
        )
        assertTrue(payload.contains("\"install_id\""))
        assertTrue(payload.contains("\"version_name\":\"0.8.1\""))
        assertTrue(payload.contains("\"version_code\":7"))
        assertTrue(payload.contains("\"channel\":\"alpha\""))
        assertFalse(payload.contains("email"))
        assertFalse(payload.contains("android_id"))
    }
}
