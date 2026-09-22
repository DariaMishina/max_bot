package ru.tarotsphere.app

import android.os.Bundle
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

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
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
}
