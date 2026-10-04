package ru.tarotsphere.app

import android.app.Application
import com.vk.id.VKID
import ru.tarotsphere.app.data.di.AppContainer

class TarotSphereApp : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        VKID.init(this)
        container = AppContainer(this)
    }
}
