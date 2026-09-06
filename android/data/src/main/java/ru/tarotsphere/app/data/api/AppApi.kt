package ru.tarotsphere.app.data.api

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
    suspend fun history(): HistoryResponseDto

    @GET("v1/catalog")
    suspend fun catalog(): CatalogDto
}
