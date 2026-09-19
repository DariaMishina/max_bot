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
    @SerialName("next_before_id") val nextBeforeId: Long? = null,
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
    val consultations: List<CatalogPackageDto> = emptyList(),
    @SerialName("tarologist_url") val tarologistUrl: String? = null,
) {
    fun toDomain() = Catalog(
        packages = packages.map { it.toDomain() },
        paymentMethods = paymentMethods,
        consultations = consultations.map { it.toDomain() },
        tarologistUrl = tarologistUrl,
    )
}

@Serializable
data class ApiErrorDto(
    val error: String = "error",
    val message: String = "",
)

@Serializable
data class TarotCardDto(val id: String, val name: String, @SerialName("image_url") val imageUrl: String = "") {
    // Use the configured HTTPS origin: a reverse proxy can report an internal HTTP URL.
    fun toDomain() = ru.tarotsphere.app.domain.model.TarotCard(
        id, name, ru.tarotsphere.app.data.BuildConfig.API_BASE_URL + "static/images/$id.png",
    )
}
@Serializable
data class DeckDto(val cards: List<TarotCardDto>)
@Serializable
data class TarotRequestDto(
    val question: String, val selection: String,
    @SerialName("card_ids") val cardIds: List<String>? = null,
    @SerialName("request_id") val requestId: String,
)
@Serializable
data class FollowUpRequestDto(val question: String, @SerialName("request_id") val requestId: String)
@Serializable
data class FeedbackRequestDto(val message: String)
@Serializable
data class FollowUpDto(val question: String, val answer: String) {
    fun toDomain() = ru.tarotsphere.app.domain.model.FollowUp(question, answer)
}
@Serializable
data class FollowUpsDto(
    @SerialName("follow_ups") val followUps: List<FollowUpDto>,
    @SerialName("follow_ups_remaining") val remaining: Int,
)
@Serializable
data class ReadingDto(
    val id: Long = 0,
    @SerialName("divination_id") val divinationId: Long = 0,
    val question: String,
    val cards: List<TarotCardDto>,
    val interpretation: String,
    @SerialName("is_free") val isFree: Boolean = true,
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("follow_ups") val followUps: List<FollowUpDto> = emptyList(),
    @SerialName("follow_ups_remaining") val remaining: Int = 0,
    val balance: BalanceDto? = null,
) {
    val readingId get() = if (id > 0) id else divinationId
    fun toDomain() = ru.tarotsphere.app.domain.model.Reading(
        readingId, question, cards.map { it.toDomain() }, interpretation, isFree, createdAt,
        followUps.map { it.toDomain() }, remaining, balance?.toDomain(),
    )
}
