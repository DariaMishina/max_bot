package ru.tarotsphere.app

import android.os.Bundle
import android.content.Intent
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.SystemBarStyle
import android.graphics.Color
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import ru.tarotsphere.app.ui.navigation.TarotNavHost
import ru.tarotsphere.app.ui.theme.Night
import ru.tarotsphere.app.ui.theme.TarotSphereTheme
import ru.rustore.sdk.pay.RuStorePayClient
import ru.rustore.sdk.pay.model.SdkTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (BuildConfig.RUSTORE_BILLING_CONFIGURED && savedInstanceState == null) {
            RuStorePayClient.instance.getIntentInteractor().proceedIntent(intent, SdkTheme.LIGHT)
        }
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.light(Color.TRANSPARENT, Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.light(0xFFF6F1E8.toInt(), 0xFFF6F1E8.toInt()),
        )
        val app = application as TarotSphereApp
        setContent {
            TarotSphereTheme {
                Surface(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(Night),
                    color = Night,
                ) {
                    TarotNavHost(container = app.container)
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (BuildConfig.RUSTORE_BILLING_CONFIGURED) {
            RuStorePayClient.instance.getIntentInteractor().proceedIntent(intent, SdkTheme.LIGHT)
        }
    }
}
