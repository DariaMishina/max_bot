package ru.tarotsphere.app.ui

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import ru.tarotsphere.app.domain.model.TokenPair
import ru.tarotsphere.app.domain.repository.AuthRepository
import ru.tarotsphere.app.domain.session.OnboardingStore
import ru.tarotsphere.app.domain.usecase.EnsureGuestSessionUseCase
import ru.tarotsphere.app.ui.session.SessionViewModel

@OptIn(ExperimentalCoroutinesApi::class)
class SessionViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @Before fun setup() { Dispatchers.setMain(dispatcher) }
    @After fun teardown() { Dispatchers.resetMain() }

    @Test fun completedOnboardingWithoutAccountOpensAuth() = runTest(dispatcher) {
        val auth = FakeAuth(confirmed = false)
        val model = SessionViewModel(EnsureGuestSessionUseCase(auth), auth, FakeOnboarding(true))
        runCurrent()
        assertTrue(model.state.value.needsAuth)
        assertFalse(model.state.value.ready)
    }

    @Test fun emailCodeConfirmationOpensMainApp() = runTest(dispatcher) {
        val auth = FakeAuth(confirmed = false)
        val model = SessionViewModel(EnsureGuestSessionUseCase(auth), auth, FakeOnboarding(true))
        runCurrent()
        model.email("reader@example.test")
        model.requestEmailCode()
        runCurrent()
        assertTrue(model.state.value.codeSent)
        model.code("123456")
        model.confirmEmail()
        runCurrent()
        assertTrue(model.state.value.ready)
        assertFalse(model.state.value.needsAuth)
    }
}

private class FakeOnboarding(private var done: Boolean) : OnboardingStore {
    override fun isCompleted() = done
    override fun markCompleted() { done = true }
}

private class FakeAuth(private val confirmed: Boolean) : AuthRepository {
    override fun hasAccessToken() = confirmed
    override fun currentUserId(): String? = if (confirmed) "user" else null
    override suspend fun restoreConfirmedSession() = confirmed
    override suspend fun requestEmailCode(email: String) = Unit
    override suspend fun confirmEmail(email: String, code: String) =
        TokenPair("access", "refresh", "user", 3600, null)
    override suspend fun refreshSession() = TokenPair("access", "refresh", "user", 3600, null)
}
