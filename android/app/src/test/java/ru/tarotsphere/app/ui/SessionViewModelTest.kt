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

    @Test fun passwordRegistrationRejectsMismatchThenClearsSecretsOnSuccess() = runTest(dispatcher) {
        val auth = FakeAuth(confirmed = false)
        val model = SessionViewModel(EnsureGuestSessionUseCase(auth), auth, FakeOnboarding(true))
        runCurrent()
        model.registering(true)
        model.login("Reader_1")
        model.password("long password 123")
        model.passwordConfirmation("different password")
        model.authenticatePassword()
        runCurrent()
        assertFalse(model.state.value.ready)
        assertTrue(model.state.value.error!!.contains("не совпадают"))
        model.passwordConfirmation("long password 123")
        model.authenticatePassword()
        runCurrent()
        assertTrue(model.state.value.ready)
        assertTrue(model.state.value.password.isEmpty())
        assertTrue(model.state.value.passwordConfirmation.isEmpty())
    }

    @Test fun passwordLoginDoesNotRequireEmailOrConfirmation() = runTest(dispatcher) {
        val auth = FakeAuth(confirmed = false)
        val model = SessionViewModel(EnsureGuestSessionUseCase(auth), auth, FakeOnboarding(true))
        runCurrent()
        model.login("Reader_1")
        model.password("long password 123")
        model.authenticatePassword()
        runCurrent()
        assertTrue(model.state.value.ready)
    }

    @Test fun passwordLoginAcceptsExpandedLoginAndEightCharacterPassword() = runTest(dispatcher) {
        val auth = FakeAuth(confirmed = false)
        val model = SessionViewModel(EnsureGuestSessionUseCase(auth), auth, FakeOnboarding(true))
        runCurrent()
        model.login("User.Name-1@example.test")
        model.password("12345678")
        model.authenticatePassword()
        runCurrent()
        assertTrue(model.state.value.ready)
    }

    @Test fun passwordLoginStillRejectsTooShortCredentials() = runTest(dispatcher) {
        val auth = FakeAuth(confirmed = false)
        val model = SessionViewModel(EnsureGuestSessionUseCase(auth), auth, FakeOnboarding(true))
        runCurrent()
        model.login("ab")
        model.password("1234567")
        model.authenticatePassword()
        runCurrent()
        assertFalse(model.state.value.ready)
        assertTrue(model.state.value.error!!.contains("Логин"))
    }

    @Test fun vkConfirmationOpensMainApp() = runTest(dispatcher) {
        val auth = FakeAuth(confirmed = false)
        val model = SessionViewModel(EnsureGuestSessionUseCase(auth), auth, FakeOnboarding(true))
        runCurrent()
        model.beginVkAuth()
        model.confirmVk("vk-access-token")
        runCurrent()
        assertTrue(model.state.value.ready)
        assertFalse(model.state.value.submitting)
    }
}

private class FakeOnboarding(private var done: Boolean) : OnboardingStore {
    override fun isCompleted() = done
    override fun markCompleted() { done = true }
}

private class FakeAuth(private val confirmed: Boolean) : AuthRepository {
    override suspend fun recoveryStart(binding: Boolean, login: String, email: String, password: String) = "challenge"
    override suspend fun recoveryConfirm(binding: Boolean, challengeId: String, code: String, password: String) = Unit
    override fun hasAccessToken() = confirmed
    override fun currentUserId(): String? = if (confirmed) "user" else null
    override suspend fun restoreConfirmedSession() = confirmed
    override suspend fun requestEmailCode(email: String) = Unit
    override suspend fun confirmEmail(email: String, code: String) =
        TokenPair("access", "refresh", "user", 3600, null)
    override suspend fun confirmVk(accessToken: String) =
        TokenPair("access", "refresh", "user", 3600, null)
    override suspend fun refreshSession() = TokenPair("access", "refresh", "user", 3600, null)
    override suspend fun authenticatePassword(login: String, password: String, registering: Boolean) =
        TokenPair("access", "refresh", "user", 3600, null)
}
