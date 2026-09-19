package ru.tarotsphere.app.ui

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.*
import org.junit.*
import org.junit.Assert.*
import ru.tarotsphere.app.domain.model.*
import ru.tarotsphere.app.domain.repository.UserRepository
import ru.tarotsphere.app.ui.history.HistoryViewModel
import ru.tarotsphere.app.ui.profile.ProfileViewModel

@OptIn(ExperimentalCoroutinesApi::class)
class ProfileHistoryViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    @Before fun setup() { Dispatchers.setMain(dispatcher) }
    @After fun teardown() { Dispatchers.resetMain() }

    @Test fun cachedHistoryStaysVisibleWhenRefreshFails() = runTest(dispatcher) {
        val repo = FakeUser().apply { pageError = AppFailure("network", "offline") }
        val model = HistoryViewModel(repo)
        runCurrent(); model.refresh(); runCurrent()
        assertEquals(1, model.state.value.items.size)
        assertNotNull(model.state.value.error)
        assertFalse(model.state.value.loading)
        repo.history.value = repo.history.value + HistoryItem(2, "Таро", "Q2", "", true)
        runCurrent()
        assertEquals(2, model.state.value.items.size)
    }
    @Test fun historyLoadsNextPageWithServerCursor() = runTest(dispatcher) {
        val repo = FakeUser()
        val model = HistoryViewModel(repo)
        model.refresh(); runCurrent(); model.loadMore(); runCurrent()
        assertEquals(listOf(null, 100L), repo.cursors)
    }
    @Test fun deleteFailureKeepsProfileAndDoesNotSignalLogout() = runTest(dispatcher) {
        val repo = FakeUser().apply { deleteError = AppFailure("network", "offline") }
        val model = ProfileViewModel(repo)
        model.refresh(); runCurrent(); model.deleteData(); model.deleteData(); runCurrent()
        assertEquals(1, repo.deletes)
        assertFalse(model.state.value.deleted)
        assertNotNull(model.state.value.profile)
        assertNotNull(model.state.value.deleteError)
    }
    @Test fun successfulDeletionClearsProfileAndSignalsNewOnboarding() = runTest(dispatcher) {
        val model = ProfileViewModel(FakeUser())
        model.refresh(); runCurrent(); model.deleteData(); runCurrent()
        assertTrue(model.state.value.deleted)
        assertNull(model.state.value.profile)
        assertEquals("", model.state.value.feedback)
    }
    @Test fun feedbackFailureKeepsDraftAndSuccessClearsIt() = runTest(dispatcher) {
        val repo = FakeUser().apply { feedbackError = AppFailure("network", "offline") }
        val model = ProfileViewModel(repo)
        model.feedback("Сообщение"); model.sendFeedback(); model.sendFeedback(); runCurrent()
        assertEquals(1, repo.feedbackCalls)
        assertEquals("Сообщение", model.state.value.feedback)
        repo.feedbackError = null
        model.sendFeedback(); runCurrent()
        assertEquals("", model.state.value.feedback)
        assertTrue(model.state.value.feedbackMessage!!.contains("Спасибо"))
    }
}
private class FakeUser : UserRepository {
    val history = MutableStateFlow(listOf(HistoryItem(1, "Таро", "Q", "", true)))
    val cursors = mutableListOf<Long?>()
    var pageError: Exception? = null
    var deleteError: Exception? = null
    var feedbackError: Exception? = null
    var deletes = 0
    var feedbackCalls = 0
    override suspend fun me() = Loaded(UserProfile("guest", true, balance()))
    override suspend fun balance() = Balance(3, 0, null, 0)
    override fun observeHistory() = history
    override suspend fun refreshHistory(beforeId: Long?): Long? {
        cursors += beforeId
        pageError?.let { throw it }
        return if (beforeId == null) 100L else null
    }
    override suspend fun feedback(message: String) { feedbackCalls++; feedbackError?.let { throw it } }
    override suspend fun deleteData() { deletes++; deleteError?.let { throw it } }
}
