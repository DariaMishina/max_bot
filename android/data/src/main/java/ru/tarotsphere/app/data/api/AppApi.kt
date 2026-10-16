package ru.tarotsphere.app.data.api

import retrofit2.http.DELETE
import retrofit2.http.Path
import retrofit2.http.Query
import ru.tarotsphere.app.data.api.dto.*
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import ru.tarotsphere.app.data.api.dto.BalanceDto
import ru.tarotsphere.app.data.api.dto.CatalogDto
import ru.tarotsphere.app.data.api.dto.GuestRequestDto
import ru.tarotsphere.app.data.api.dto.HistoryResponseDto
import ru.tarotsphere.app.data.api.dto.MeDto
import ru.tarotsphere.app.data.api.dto.RefreshRequestDto
import ru.tarotsphere.app.data.api.dto.TokenPairDto

interface AppApi {
    @POST("v1/me/recovery-email/start")
    suspend fun recoveryEmailStart(@Body body: RecoveryRequestDto): RecoveryResponseDto
    @POST("v1/me/recovery-email/confirm")
    suspend fun recoveryEmailConfirm(@Body body: RecoveryRequestDto): RecoveryResponseDto
    @POST("v1/auth/password/reset/start")
    suspend fun passwordResetStart(@Body body: RecoveryRequestDto): RecoveryResponseDto
    @POST("v1/auth/password/reset/confirm")
    suspend fun passwordResetConfirm(@Body body: RecoveryRequestDto): RecoveryResponseDto
    @POST("v1/auth/password/register")
    suspend fun passwordRegister(@Body body: PasswordAuthRequestDto): TokenPairDto

    @POST("v1/auth/password/login")
    suspend fun passwordLogin(@Body body: PasswordAuthRequestDto): TokenPairDto

    @POST("v1/telemetry/app-open")
    suspend fun appOpen(@Body body: AppOpenRequestDto): AppOpenResponseDto

    @POST("v1/auth/guest")
    suspend fun guest(@Body body: GuestRequestDto): TokenPairDto

    @POST("v1/auth/refresh")
    suspend fun refresh(@Body body: RefreshRequestDto): TokenPairDto

    @POST("v1/auth/email/start")
    suspend fun emailStart(@Body body: EmailStartRequestDto): EmailStartResponseDto

    @POST("v1/auth/email/confirm")
    suspend fun emailConfirm(@Body body: EmailConfirmRequestDto): TokenPairDto

    @POST("v1/auth/vk")
    suspend fun vkAuth(@Body body: VkAuthRequestDto): TokenPairDto

    @POST("v1/auth/logout")
    suspend fun logout(@Body body: RefreshRequestDto)

    @GET("v1/me")
    suspend fun me(): MeDto

    @GET("v1/me/balance")
    suspend fun balance(): BalanceDto

    @GET("v1/me/history")
    suspend fun history(@Query("before_id") beforeId: Long? = null): HistoryResponseDto

    @GET("v1/catalog")
    suspend fun catalog(@Query("include_test_contact") includeTestContact: Boolean = false): CatalogDto

    @POST("v1/billing/rustore/verify")
    suspend fun verifyRustore(@Body body: RustoreVerifyRequestDto): PaymentResultDto
    @GET("v1/tarot/deck")
    suspend fun deck(@Query("scope") scope: String? = null): DeckDto

    @POST("v1/divinations/tarot")
    suspend fun tarot(@Body body: TarotRequestDto): ReadingDto

    @GET("v1/divinations/{id}")
    suspend fun detail(@Path("id") id: Long): ReadingDto

    @POST("v1/divinations/{id}/follow-up")
    suspend fun followUp(@Path("id") id: Long, @Body body: FollowUpRequestDto): FollowUpsDto

    @POST("v1/me/feedback")
    suspend fun feedback(@Body body: FeedbackRequestDto)

    @DELETE("v1/me")
    suspend fun deleteMe()
}
