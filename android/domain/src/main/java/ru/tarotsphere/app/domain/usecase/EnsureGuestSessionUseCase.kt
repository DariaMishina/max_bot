package ru.tarotsphere.app.domain.usecase

import ru.tarotsphere.app.domain.model.TokenPair
import ru.tarotsphere.app.domain.repository.AuthRepository

class EnsureGuestSessionUseCase(
    private val authRepository: AuthRepository,
) {
    suspend operator fun invoke(): TokenPair = authRepository.ensureGuestSession()
}
