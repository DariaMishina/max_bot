package ru.tarotsphere.app.domain.session

interface OnboardingStore {
    fun isCompleted(): Boolean
    fun markCompleted()
}
