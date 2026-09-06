package ru.tarotsphere.app.domain.model

data class UserProfile(
    val userId: String,
    val isGuest: Boolean,
    val balance: Balance,
)
