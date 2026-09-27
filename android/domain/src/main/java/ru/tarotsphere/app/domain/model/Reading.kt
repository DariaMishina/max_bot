package ru.tarotsphere.app.domain.model

data class TarotCard(val id: String, val name: String, val imageUrl: String)
enum class CardSelectionMode(val wireValue: String) {
    RANDOM("random"),
    INTUITIVE("manual"),
    NAMED("named"),
}
data class FollowUp(val question: String, val answer: String)
data class Reading(
    val id: Long,
    val question: String,
    val cards: List<TarotCard>,
    val interpretation: String,
    val isFree: Boolean,
    val createdAt: String,
    val followUps: List<FollowUp>,
    val followUpsRemaining: Int,
    val balance: Balance? = null,
)
data class Loaded<T>(val value: T, val fromCache: Boolean = false)
class AppFailure(val code: String, override val message: String) : Exception(message)
