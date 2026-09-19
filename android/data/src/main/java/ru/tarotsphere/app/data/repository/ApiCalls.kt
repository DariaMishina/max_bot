package ru.tarotsphere.app.data.repository

import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.serialization.json.Json
import retrofit2.HttpException
import ru.tarotsphere.app.data.api.dto.ApiErrorDto
import ru.tarotsphere.app.domain.model.AppFailure

private val errorJson = Json { ignoreUnknownKeys = true }

internal fun Exception.allowsCache() = this is IOException || (this is HttpException && code() >= 500)

internal suspend fun <T> apiCall(block: suspend () -> T): T = try {
    block()
} catch (e: CancellationException) {
    throw e
} catch (e: HttpException) {
    val body = runCatching { errorJson.decodeFromString<ApiErrorDto>(e.response()?.errorBody()?.string().orEmpty()) }.getOrNull()
    val code = body?.error ?: "http_${e.code()}"
    val message = when {
        code == "no_balance" -> "Расклады закончились. Выберите пакет в магазине."
        code == "follow_up_limit" -> "Все уточнения к этому раскладу использованы."
        e.code() == 401 -> "Не удалось подтвердить сессию. Перезапустите приложение при подключённом интернете."
        e.code() == 404 -> "Данные не найдены. Обновите экран."
        e.code() >= 500 -> "Сервер временно недоступен. Попробуйте позже."
        else -> body?.message?.takeIf { it.isNotBlank() } ?: "Не удалось выполнить запрос. Попробуйте снова."
    }
    throw AppFailure(code, message)
} catch (e: IOException) {
    throw AppFailure("network", "Нет связи с сервером. Проверьте интернет и повторите попытку.")
}
