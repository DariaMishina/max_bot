package ru.tarotsphere.app.domain.model

data class TokenPair(
    val accessToken: String,
    val refreshToken: String,
    val userId: String,
    val expiresIn: Int,
    val balance: Balance?,
)
