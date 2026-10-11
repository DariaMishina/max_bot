plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    id("vkid.manifest.placeholders")
}

val rustoreConsoleAppId = providers.gradleProperty("RUSTORE_CONSOLE_APP_ID").orElse("2063751721").get()

android {
    namespace = "ru.tarotsphere.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "ru.tarotsphere.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 6
        versionName = "0.8.0"
        manifestPlaceholders["rustoreConsoleAppId"] = rustoreConsoleAppId
        buildConfigField("boolean", "RUSTORE_BILLING_CONFIGURED", (rustoreConsoleAppId != "0").toString())
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
        debug {
            versionNameSuffix = "-debug"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    implementation(project(":domain"))
    implementation(libs.coil.compose)
    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    implementation(project(":data"))
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation(libs.androidx.material.icons.extended)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.vkid)
    implementation(platform(libs.rustore.bom))
    implementation(libs.rustore.pay)
    debugImplementation(libs.androidx.ui.tooling)
}
