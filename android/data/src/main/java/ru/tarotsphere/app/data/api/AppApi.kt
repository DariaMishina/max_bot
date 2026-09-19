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
    @POST("v1/auth/guest")
    suspend fun guest(@Body body: GuestRequestDto): TokenPairDto

    @POST("v1/auth/refresh")
    suspend fun refresh(@Body body: RefreshRequestDto): TokenPairDto

    @GET("v1/me")
    suspend fun me(): MeDto

    @GET("v1/me/balance")
    suspend fun balance(): BalanceDto

    @GET("v1/me/history")
    suspend fun history(@Query("before_id") beforeId: Long? = null): HistoryResponseDto

    @GET("v1/catalog")
    suspend fun catalog(): CatalogDto
    @GET("v1/tarot/deck")
    suspend fun deck(): DeckDto

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
