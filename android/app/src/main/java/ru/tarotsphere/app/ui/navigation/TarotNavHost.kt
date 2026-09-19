package ru.tarotsphere.app.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import ru.tarotsphere.app.data.di.AppContainer
import ru.tarotsphere.app.ui.main.MainScaffold
import ru.tarotsphere.app.ui.onboarding.OnboardingScreen
import ru.tarotsphere.app.ui.session.SessionViewModel
import ru.tarotsphere.app.ui.session.SplashScreen

private object Dest {
    const val Splash = "splash"
    const val Onboarding = "onboarding"
    const val Main = "main"
}

@Composable
fun TarotNavHost(container: AppContainer) {
    val nav = rememberNavController()
    val session: SessionViewModel = viewModel(
        factory = SessionViewModel.factory(container.ensureGuestSession, container.onboardingStore),
    )
    val state by session.state.collectAsStateWithLifecycle()

    LaunchedEffect(state.needsOnboarding, state.ready, state.error) {
        val dest = nav.currentDestination?.route
        when {
            state.needsOnboarding && dest != Dest.Onboarding -> nav.navigate(Dest.Onboarding) {
                popUpTo(0) { inclusive = true }
            }
            state.ready && dest != Dest.Main -> nav.navigate(Dest.Main) {
                popUpTo(0) { inclusive = true }
            }
            !state.needsOnboarding && !state.ready && dest != Dest.Splash -> nav.navigate(Dest.Splash) {
                popUpTo(0) { inclusive = true }
            }
        }
    }

    NavHost(navController = nav, startDestination = Dest.Splash) {
        composable(Dest.Splash) {
            SplashScreen(state = state, onRetry = session::retry)
        }
        composable(Dest.Onboarding) {
            OnboardingScreen(onFinished = session::completeOnboarding)
        }
        composable(Dest.Main) {
            MainScaffold(container, onDeleted = session::start)
        }
    }
}
