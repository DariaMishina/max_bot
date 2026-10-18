import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    id("vkid.manifest.placeholders")
}

val rustoreConsoleAppId = providers.gradleProperty("RUSTORE_CONSOLE_APP_ID").orElse("2063751721").get()
val explicitReleaseApiUrl = providers.gradleProperty("APP_API_BASE_URL").orNull?.trim()
val releaseChannel = providers.gradleProperty("APP_RELEASE_CHANNEL").orNull?.trim()
val appBuildChannel = releaseChannel ?: "debug"
val stagingApiUrl = providers.gradleProperty("APP_STAGING_API_BASE_URL")
    .orElse("https://01a0ba9c-b091-79dc-9a97-07e3b1eba847.tunnel4.com/")
    .get().trimEnd('/') + "/"
val releaseKeystorePropertiesFile = rootProject.file("keystore.properties")
val localEnvFile = rootProject.file("../.env")
val releaseKeystoreProperties = Properties().apply {
    if (releaseKeystorePropertiesFile.isFile) {
        releaseKeystorePropertiesFile.inputStream().use(::load)
    }
}

fun localSecret(name: String): String? =
    providers.environmentVariable(name).orNull?.takeIf(String::isNotBlank)
        ?: localEnvFile.takeIf(File::isFile)?.useLines { lines ->
            lines
                .map(String::trim)
                .firstOrNull { it.startsWith("$name=") }
                ?.substringAfter('=')
                ?.trim()
                ?.takeIf(String::isNotBlank)
        }

fun releaseSigningProperty(name: String): String =
    releaseKeystoreProperties.getProperty(name)?.takeIf(String::isNotBlank)
        ?: error("Missing '$name' in ${releaseKeystorePropertiesFile.path}")

val releaseStorePassword = localSecret("ANDROID_RELEASE_STORE_PASSWORD")
val releaseKeyPassword = localSecret("ANDROID_RELEASE_KEY_PASSWORD")
val releaseSigningConfigured =
    releaseKeystorePropertiesFile.isFile && releaseStorePassword != null && releaseKeyPassword != null
val releaseTaskRequested = gradle.startParameter.taskNames.any { taskName ->
    taskName.endsWith("assembleRelease", ignoreCase = true) ||
        taskName.endsWith("bundleRelease", ignoreCase = true)
}

if (releaseTaskRequested) {
    check(releaseSigningConfigured) {
        "Release signing is not configured. Create android/keystore.properties first."
    }
    check(!explicitReleaseApiUrl.isNullOrBlank()) {
        "Release API URL must be explicit: pass -PAPP_API_BASE_URL=https://production.example/"
    }
    check(releaseChannel in setOf("alpha", "production")) {
        "Release channel must be explicit: pass -PAPP_RELEASE_CHANNEL=alpha or production"
    }
    check(explicitReleaseApiUrl.startsWith("https://") &&
        !explicitReleaseApiUrl.contains("localhost") &&
        !explicitReleaseApiUrl.contains("127.0.0.1")) {
        "Release API URL must be a public HTTPS origin."
    }
    if (releaseChannel == "alpha") {
        check(explicitReleaseApiUrl.trimEnd('/') + "/" == stagingApiUrl) {
            "Alpha release must use the configured staging API URL."
        }
    } else {
        check(explicitReleaseApiUrl.trimEnd('/') + "/" != stagingApiUrl) {
            "Production release must not use the staging API URL."
        }
    }
}

android {
    namespace = "ru.tarotsphere.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "ru.tarotsphere.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 9
        versionName = "0.8.3"
        manifestPlaceholders["rustoreConsoleAppId"] = rustoreConsoleAppId
        buildConfigField("boolean", "RUSTORE_BILLING_CONFIGURED", (rustoreConsoleAppId != "0").toString())
        buildConfigField("String", "APP_RELEASE_CHANNEL", "\"$appBuildChannel\"")
    }

    signingConfigs {
        if (releaseSigningConfigured) {
            create("release") {
                storeFile = rootProject.file(releaseSigningProperty("storeFile"))
                storePassword = releaseStorePassword
                keyAlias = releaseSigningProperty("keyAlias")
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.findByName("release")
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
