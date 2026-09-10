package ru.tarotsphere.app.ui.main

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Storefront
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.lifecycle.viewmodel.compose.viewModel
import ru.tarotsphere.app.data.di.AppContainer
import ru.tarotsphere.app.ui.history.HistoryScreen
import ru.tarotsphere.app.ui.history.HistoryViewModel
import ru.tarotsphere.app.ui.profile.ProfileScreen
import ru.tarotsphere.app.ui.profile.ProfileViewModel
import ru.tarotsphere.app.ui.shop.ShopScreen
import ru.tarotsphere.app.ui.shop.ShopViewModel
import ru.tarotsphere.app.ui.spread.SpreadScreen
import ru.tarotsphere.app.ui.spread.SpreadViewModel
import ru.tarotsphere.app.ui.theme.CreamMuted
import ru.tarotsphere.app.ui.theme.Gold
import ru.tarotsphere.app.ui.theme.Night
import ru.tarotsphere.app.ui.theme.NightElevated

private data class Tab(val label: String, val icon: ImageVector)

private val Tabs = listOf(
    Tab("Расклад", Icons.Outlined.AutoAwesome),
    Tab("История", Icons.Outlined.History),
    Tab("Магазин", Icons.Outlined.Storefront),
    Tab("Профиль", Icons.Outlined.Person),
)

@Composable
fun MainScaffold(container: AppContainer) {
    var selected by rememberSaveable { mutableIntStateOf(0) }

    Scaffold(
        containerColor = Night,
        bottomBar = {
            NavigationBar(containerColor = NightElevated) {
                Tabs.forEachIndexed { index, tab ->
                    NavigationBarItem(
                        selected = selected == index,
                        onClick = { selected = index },
                        icon = { Icon(tab.icon, contentDescription = tab.label) },
                        label = { Text(tab.label) },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = Gold,
                            selectedTextColor = Gold,
                            unselectedIconColor = CreamMuted,
                            unselectedTextColor = CreamMuted,
                            indicatorColor = Gold.copy(alpha = 0.15f),
                        ),
                    )
                }
            }
        },
    ) { padding ->
        Box(Modifier.padding(padding)) {
            when (selected) {
                0 -> SpreadRoute(container)
                1 -> HistoryRoute(container)
                2 -> ShopRoute(container)
                else -> ProfileRoute(container)
            }
        }
    }
}

@Composable
private fun SpreadRoute(container: AppContainer) {
    val viewModel: SpreadViewModel = viewModel(
        factory = SpreadViewModel.factory(container.userRepository),
    )
    SpreadScreen(viewModel)
}

@Composable
private fun HistoryRoute(container: AppContainer) {
    val viewModel: HistoryViewModel = viewModel(
        factory = HistoryViewModel.factory(container.userRepository),
    )
    HistoryScreen(viewModel)
}

@Composable
private fun ShopRoute(container: AppContainer) {
    val viewModel: ShopViewModel = viewModel(
        factory = ShopViewModel.factory(container.catalogRepository),
    )
    ShopScreen(viewModel)
}

@Composable
private fun ProfileRoute(container: AppContainer) {
    val viewModel: ProfileViewModel = viewModel(
        factory = ProfileViewModel.factory(container.userRepository),
    )
    ProfileScreen(viewModel)
}
