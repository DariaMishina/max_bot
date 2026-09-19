package ru.tarotsphere.app.ui

import androidx.lifecycle.SavedStateHandle
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import ru.tarotsphere.app.domain.model.*
import ru.tarotsphere.app.domain.repository.ReadingRepository
import ru.tarotsphere.app.ui.spread.SpreadViewModel
import ru.tarotsphere.app.ui.reading.ReadingViewModel

@OptIn(ExperimentalCoroutinesApi::class)
class MvpViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    @Before fun setup() { Dispatchers.setMain(dispatcher) }
    @After fun teardown() { Dispatchers.resetMain() }

    @Test fun blankQuestionDoesNotSendRequest() = runTest(dispatcher) {
        val repo = FakeReadings()
        val model = SpreadViewModel(repo, SavedStateHandle())
        model.question("  "); model.submit(); runCurrent()
        assertTrue(repo.requests.isEmpty())
        assertNotNull(model.state.value.error)
    }
    @Test fun manualSelectionAllowsThreeUniqueCardsAndDeselection() = runTest(dispatcher) {
        val model = SpreadViewModel(FakeReadings(), SavedStateHandle())
        model.mode(true); runCurrent()
        listOf("0", "1", "2", "3").forEach(model::select)
        assertEquals(listOf("0", "1", "2"), model.state.value.selectedIds)
        model.select("1"); model.select("3")
        assertEquals(listOf("0", "2", "3"), model.state.value.selectedIds)
    }
    @Test fun doubleTapIsIgnoredAndNetworkRetryUsesSameRequestId() = runTest(dispatcher) {
        val repo = FakeReadings().apply { createError = AppFailure("network", "offline") }
        val model = SpreadViewModel(repo, SavedStateHandle())
        model.question("Что дальше?"); model.submit(); model.submit(); runCurrent()
        assertEquals(1, repo.requests.size)
        model.question("Изменение во время неопределённого ответа")
        assertEquals("Что дальше?", model.state.value.question)
        repo.createError = null
        model.submit(); runCurrent()
        assertEquals(repo.requests[0], repo.requests[1])
        assertEquals(42L, model.state.value.resultId)
    }
    @Test fun pendingManualRequestSurvivesProcessRecreation() = runTest(dispatcher) {
        val repo = FakeReadings()
        val handle = SavedStateHandle(mapOf("question" to "Q", "manual" to true, "selected" to arrayListOf("a", "b", "c"), "request" to "stable-key", "pending" to true))
        val model = SpreadViewModel(repo, handle)
        runCurrent(); model.submit(); runCurrent()
        assertEquals(listOf("a", "b", "c"), repo.lastCardIds)
        assertEquals("stable-key", repo.requests.single())
    }
    @Test fun noBalanceOpensShopButLastSuccessfulResultRemainsReadable() = runTest(dispatcher) {
        val repo = FakeReadings().apply { createError = AppFailure("no_balance", "empty") }
        val model = SpreadViewModel(repo, SavedStateHandle())
        model.question("Q"); model.submit(); runCurrent()
        assertTrue(model.state.value.needsShop)
        assertFalse(model.state.value.retryPending)
        model.consumeShop(); repo.createError = null
        model.submit(); runCurrent()
        assertEquals(42L, model.state.value.resultId)
        assertFalse(model.state.value.needsShop)
    }
    @Test fun followUpRetryKeepsKeyAndCounterComesFromServer() = runTest(dispatcher) {
        val repo = FakeReadings().apply { followError = AppFailure("network", "offline") }
        val model = ReadingViewModel(42, repo, SavedStateHandle())
        model.refresh(); runCurrent(); model.question("Уточнение"); model.send(); model.send(); runCurrent()
        assertEquals(1, repo.followRequests.size)
        assertEquals(2, model.state.value.reading!!.followUpsRemaining)
        repo.followError = null
        model.send(); runCurrent()
        assertEquals(repo.followRequests[0], repo.followRequests[1])
        assertEquals(1, model.state.value.reading!!.followUpsRemaining)
        assertEquals("", model.state.value.question)
    }
    @Test fun exhaustedFollowUpDisablesFurtherRequests() = runTest(dispatcher) {
        val repo = FakeReadings().apply { followError = AppFailure("follow_up_limit", "limit") }
        val model = ReadingViewModel(42, repo, SavedStateHandle())
        model.refresh(); runCurrent(); model.question("Q"); model.send(); runCurrent()
        model.send(); runCurrent()
        assertEquals(1, repo.followRequests.size)
        assertEquals(0, model.state.value.reading!!.followUpsRemaining)
        assertFalse(model.state.value.retryPending)
    }
}

private class FakeReadings : ReadingRepository {
    val requests = mutableListOf<String>()
    val followRequests = mutableListOf<String>()
    var lastCardIds: List<String>? = null
    var createError: Exception? = null
    var followError: Exception? = null
    val reading = Reading(42, "Q", emptyList(), "Text", true, "2026-09-13T12:00:00", emptyList(), 2)
    override suspend fun deck() = (0..8).map { TarotCard("$it", "Card $it", "") }
    override suspend fun create(question: String, cardIds: List<String>?, requestId: String): Reading {
        requests += requestId; lastCardIds = cardIds
        createError?.let { throw it }
        return reading
    }
    override suspend fun detail(id: Long) = Loaded(reading)
    override suspend fun followUp(reading: Reading, question: String, requestId: String): Reading {
        followRequests += requestId
        followError?.let { throw it }
        return reading.copy(followUps = listOf(FollowUp(question, "Answer")), followUpsRemaining = 1)
    }
}
