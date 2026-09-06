package ru.tarotsphere.app.data.repository

import ru.tarotsphere.app.data.local.SecurePrefs
import ru.tarotsphere.app.domain.session.OnboardingStore

class OnboardingStoreImpl(
    private val prefs: SecurePrefs,
) : OnboardingStore {
    override fun isCompleted(): Boolean = prefs.isOnboardingCompleted()

    override fun markCompleted() = prefs.markOnboardingCompleted()
}
