import java.net.URI

plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.kotlin.kapt)
}

val stagingApiBaseUrl = providers.gradleProperty("APP_STAGING_API_BASE_URL")
    .orElse("https://01a0ba9c-b091-79dc-9a97-07e3b1eba847.tunnel4.com/").get().trimEnd('/') + "/"
val apiBaseUrl = providers.gradleProperty("APP_API_BASE_URL")
    .orElse(stagingApiBaseUrl).get().trimEnd('/') + "/"
for (url in listOf(stagingApiBaseUrl, apiBaseUrl)) {
    val apiUri = URI(url)
    require(apiUri.scheme == "https" && !apiUri.host.isNullOrBlank() && apiUri.rawUserInfo == null &&
        apiUri.rawQuery == null && apiUri.rawFragment == null && apiUri.path == "/") {
        "API URL must be an HTTPS origin, e.g. https://example.tunnel4.com/ (without /v1)"
    }
}

android {
    namespace = "ru.tarotsphere.app.data"
    compileSdk = 35

    defaultConfig {
        minSdk = 26
        // Постоянный адрес xTunnel; при смене URL обновить и пересобрать.
        buildConfigField(
            "String",
            "API_BASE_URL",
            "\"$apiBaseUrl\"",
        )
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        debug {
            // A release URL passed in the same invocation must never redirect the test app.
            buildConfigField("String", "API_BASE_URL", "\"$stagingApiBaseUrl\"")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation(project(":domain"))
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    kapt(libs.androidx.room.compiler)
    testImplementation(libs.junit)
    implementation(libs.androidx.security.crypto)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.retrofit)
    implementation(libs.retrofit.kotlinx)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)
}

kapt {
    arguments { arg("room.schemaLocation", "$projectDir/schemas") }
}
