package ru.tarotsphere.app.data.di

import android.content.Context
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import ru.tarotsphere.app.data.BuildConfig
import ru.tarotsphere.app.data.api.AppApi
import ru.tarotsphere.app.data.api.AuthInterceptor
import ru.tarotsphere.app.data.api.TokenAuthenticator
import ru.tarotsphere.app.data.local.SecurePrefs
import ru.tarotsphere.app.data.repository.AuthRepositoryImpl
import ru.tarotsphere.app.data.repository.CatalogRepositoryImpl
import ru.tarotsphere.app.data.repository.OnboardingStoreImpl
import ru.tarotsphere.app.data.repository.UserRepositoryImpl
import ru.tarotsphere.app.domain.repository.AuthRepository
import ru.tarotsphere.app.domain.repository.CatalogRepository
import ru.tarotsphere.app.domain.repository.UserRepository
import ru.tarotsphere.app.domain.session.OnboardingStore
import ru.tarotsphere.app.domain.usecase.EnsureGuestSessionUseCase
import java.util.concurrent.TimeUnit

class AppContainer(context: Context) {
    val prefs = SecurePrefs(context.applicationContext)

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        explicitNulls = false
    }

    private val logging = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BASIC
        redactHeader("Authorization")
    }

    private val jsonConverter = json.asConverterFactory("application/json".toMediaType())

    private val refreshClient = OkHttpClient.Builder()
        .addInterceptor(logging)
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    private val refreshApi: AppApi = Retrofit.Builder()
        .baseUrl(BuildConfig.API_BASE_URL)
        .client(refreshClient)
        .addConverterFactory(jsonConverter)
        .build()
        .create(AppApi::class.java)

    private val authedClient = OkHttpClient.Builder()
        .addInterceptor(AuthInterceptor(prefs))
        .addInterceptor(logging)
        .authenticator(TokenAuthenticator(prefs, refreshApi))
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    val api: AppApi = Retrofit.Builder()
        .baseUrl(BuildConfig.API_BASE_URL)
        .client(authedClient)
        .addConverterFactory(jsonConverter)
        .build()
        .create(AppApi::class.java)

    val authRepository: AuthRepository = AuthRepositoryImpl(api, refreshApi, prefs)
    val userRepository: UserRepository = UserRepositoryImpl(api)
    val catalogRepository: CatalogRepository = CatalogRepositoryImpl(api)
    val onboardingStore: OnboardingStore = OnboardingStoreImpl(prefs)
    val ensureGuestSession = EnsureGuestSessionUseCase(authRepository)
}
