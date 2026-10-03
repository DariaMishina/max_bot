package ru.tarotsphere.app.domain.model

data class UserProfile(
    val userId: String,
    val isGuest: Boolean,
    val balance: Balance,
    val identities: List<AccountIdentity> = emptyList(),
)

data class AccountIdentity(
    val provider: String,
    val displayValue: String,
)
