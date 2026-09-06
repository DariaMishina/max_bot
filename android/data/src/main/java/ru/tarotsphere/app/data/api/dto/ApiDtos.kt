package ru.tarotsphere.app.data.api.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import ru.tarotsphere.app.domain.model.Balance
import ru.tarotsphere.app.domain.model.Catalog
import ru.tarotsphere.app.domain.model.CatalogPackage
import ru.tarotsphere.app.domain.model.HistoryItem
import ru.tarotsphere.app.domain.model.TokenPair
import ru.tarotsphere.app.domain.model.UserProfile

@Serializable
data class GuestRequestDto(
    @SerialName("install_id") val installId: String,
)

@Serializable
data class RefreshRequestDto(
    @SerialName("refresh_token") val refreshToken: String,
)

@Serializable
data class BalanceDto(
    @SerialName("free_divinations_remaining") val freeRemaining: Int = 0,
    @SerialName("paid_divinations_remaining") val paidRemaining: Int = 0,
    @SerialName("unlimited_until") val unlimitedUntil: String? = null,
    @SerialName("total_divinations_used") val totalUsed: Int = 0,
) {
    fun toDomain() = Balance(
        freeRemaining = freeRemaining,
        paidRemaining = paidRemaining,
        unlimitedUntil = unlimitedUntil,
        totalUsed = totalUsed,
    )
}

@Serializable
data class TokenPairDto(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("token_type") val tokenType: String = "bearer",
    @SerialName("expires_in") val expiresIn: Int = 3600,
    @SerialName("user_id") val userId: String,
    val balance: BalanceDto? = null,
) {
    fun toDomain() = TokenPair(
        accessToken = accessToken,
        refreshToken = refreshToken,
        userId = userId,
        expiresIn = expiresIn,
        balance = balance?.toDomain(),
    )
}

@Serializable
data class MeDto(
    @SerialName("user_id") val userId: String,
    @SerialName("is_guest") val isGuest: Boolean = true,
    val balance: BalanceDto,
) {
    fun toDomain() = UserProfile(
        userId = userId,
        isGuest = isGuest,
        balance = balance.toDomain(),
    )
}

@Serializable
data class HistoryItemDto(
    val id: Long,
    @SerialName("divination_type") val type: String = "tarot",
    val question: String = "",
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("is_free") val isFree: Boolean = true,
) {
    fun toDomain() = HistoryItem(
        id = id,
        type = type,
        question = question,
        createdAt = createdAt,
        isFree = isFree,
    )
}

@Serializable
data class HistoryResponseDto(
    val items: List<HistoryItemDto> = emptyList(),
)

@Serializable
data class CatalogPackageDto(
    val id: String,
    val name: String,
    @SerialName("price_rub") val priceRub: Int,
    val subscription: Boolean = false,
) {
    fun toDomain() = CatalogPackage(
        id = id,
        name = name,
        priceRub = priceRub,
        isSubscription = subscription,
    )
}

@Serializable
data class CatalogDto(
    val packages: List<CatalogPackageDto> = emptyList(),
    @SerialName("payment_methods") val paymentMethods: List<String> = emptyList(),
) {
    fun toDomain() = Catalog(
        packages = packages.map { it.toDomain() },
        paymentMethods = paymentMethods,
    )
}

@Serializable
data class ApiErrorDto(
    val error: String = "error",
    val message: String = "",
)
