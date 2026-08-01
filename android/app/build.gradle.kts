import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

val googleServerClientId = providers
    .gradleProperty("PRACTENTURE_GOOGLE_SERVER_CLIENT_ID")
    .orElse(providers.environmentVariable("PRACTENTURE_GOOGLE_SERVER_CLIENT_ID"))
    .orElse("")
    .get()
    .replace("\\", "\\\\")
    .replace("\"", "\\\"")

fun releaseSigningValue(name: String): String? = providers
    .gradleProperty(name)
    .orElse(providers.environmentVariable(name))
    .orNull

val releaseSigningValues = mapOf(
    "PRACTENTURE_ANDROID_RELEASE_STORE_FILE" to releaseSigningValue("PRACTENTURE_ANDROID_RELEASE_STORE_FILE"),
    "PRACTENTURE_ANDROID_RELEASE_STORE_PASSWORD" to releaseSigningValue("PRACTENTURE_ANDROID_RELEASE_STORE_PASSWORD"),
    "PRACTENTURE_ANDROID_RELEASE_KEY_ALIAS" to releaseSigningValue("PRACTENTURE_ANDROID_RELEASE_KEY_ALIAS"),
    "PRACTENTURE_ANDROID_RELEASE_KEY_PASSWORD" to releaseSigningValue("PRACTENTURE_ANDROID_RELEASE_KEY_PASSWORD"),
)
val missingReleaseSigningValues = releaseSigningValues.filterValues { it.isNullOrBlank() }.keys

android {
    namespace = "com.practenture.android"
    compileSdk = 36
    compileSdkMinor = 1

    defaultConfig {
        applicationId = "com.practenture.android"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("String", "PRACTENTURE_BASE_URL", "\"https://practenture.com/\"")
        buildConfigField("String", "GOOGLE_SERVER_CLIENT_ID", "\"$googleServerClientId\"")
    }

    buildFeatures { compose = true; buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlin {
        compilerOptions {
            jvmTarget.set(JvmTarget.JVM_17)
            allWarningsAsErrors.set(true)
        }
    }
    packaging {
        jniLibs.keepDebugSymbols += "**/libandroidx.graphics.path.so"
    }
    signingConfigs {
        create("release") {
            if (missingReleaseSigningValues.isEmpty()) {
                storeFile = file(releaseSigningValues.getValue("PRACTENTURE_ANDROID_RELEASE_STORE_FILE")!!)
                storePassword = releaseSigningValues.getValue("PRACTENTURE_ANDROID_RELEASE_STORE_PASSWORD")
                keyAlias = releaseSigningValues.getValue("PRACTENTURE_ANDROID_RELEASE_KEY_ALIAS")
                keyPassword = releaseSigningValues.getValue("PRACTENTURE_ANDROID_RELEASE_KEY_PASSWORD")
            }
        }
    }
    buildTypes {
        getByName("release") {
            signingConfig = signingConfigs.getByName("release")
        }
    }
}

val verifyReleaseSigning by tasks.registering {
    doLast {
        check(missingReleaseSigningValues.isEmpty()) {
            "Release signing is required. Configure the missing secure Gradle property or environment variable names: " +
                missingReleaseSigningValues.sorted().joinToString(", ")
        }
    }
}

tasks.configureEach {
    if (name in setOf("assembleRelease", "bundleRelease", "signReleaseBundle")) {
        dependsOn(verifyReleaseSigning)
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.05.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.0")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    implementation("androidx.credentials:credentials:1.6.0")
    implementation("androidx.credentials:credentials-play-services-auth:1.6.0")
    implementation("com.google.android.libraries.identity.googleid:googleid:1.2.0")
    testImplementation("junit:junit:4.13.2")
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")
}
