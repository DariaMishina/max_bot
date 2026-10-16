package ru.tarotsphere.app

import android.app.Application
import android.util.Log
import com.vk.id.VKID
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import ru.tarotsphere.app.data.di.AppContainer

class TarotSphereApp : Application() {
    private val applicationScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        VKID.init(this)
        container = AppContainer(this)
        applicationScope.launch {
            runCatching {
                container.reportAppOpen(
                    versionName = BuildConfig.VERSION_NAME,
                    versionCode = BuildConfig.VERSION_CODE,
                    channel = BuildConfig.APP_RELEASE_CHANNEL,
                )
            }.onFailure { error ->
                Log.w(TAG, "App launch telemetry was not delivered", error)
            }
        }
    }

    private companion object {
        const val TAG = "TarotSphereApp"
    }
}
