pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
        maven(url = "https://nexus-external.vkteam.ru/repository/maven/")
    }
}

plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "0.9.0"
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        maven(url = "https://nexus-external.vkteam.ru/repository/maven/")
    }
}

rootProject.name = "tarot-sphere"
include(":app", ":data", ":domain")
