plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// ── Firebase, only if it has been configured ─────────────────────────────────
//
// The google-services plugin FAILS THE BUILD when it cannot find a config file, so
// applying it unconditionally would make the whole app unbuildable until someone creates
// a Firebase project. Push is an enhancement; not having it must not stop the app.
//
// Each flavour has its own applicationId (.dev / .lan / none for prod), and the plugin
// refuses a config whose client list does not contain the package being built
// ("No matching client found for package name"). So a per-flavour file is honoured too:
// register all three package names in one Firebase project and drop the single
// app/google-services.json in, or give each flavour its own under src/<flavour>/.
val firebaseConfigs = listOf(
    file("google-services.json"),
    file("src/dev/google-services.json"),
    file("src/lan/google-services.json"),
    file("src/prod/google-services.json"),
)
val firebaseConfigured = firebaseConfigs.any { it.exists() }

if (firebaseConfigured) {
    apply(plugin = "com.google.gms.google-services")
    logger.lifecycle("M-Tag: Firebase config found — push enabled.")
} else {
    logger.lifecycle(
        "M-Tag: no google-services.json — building WITHOUT push. " +
            "Add android/app/google-services.json to enable it.",
    )
}

android {
    namespace = "com.mtag.mtag_user_app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        // Required by flutter_local_notifications, which uses java.time on a minSdk that
        // predates it. Without this the build fails outright at checkAarMetadata rather
        // than misbehaving at runtime, which is the better of the two failures.
        isCoreLibraryDesugaringEnabled = true
    }

    defaultConfig {
        applicationId = "com.mtag.userapp"
        // 23 (6.0) is the floor flutter_secure_storage needs for
        // EncryptedSharedPreferences, which is where the cookie-jar marker and the
        // remembered phone number live.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        // Urdu is a first-class locale, so its resources must survive the build.
        resourceConfigurations += listOf("en", "ur")

        // Lets the Dart side distinguish "push is off because this build has no Firebase
        // config" from "push is off because the user declined permission". Without it both
        // look identical in the UI, and the first is a build mistake while the second is a
        // choice to respect.
        buildConfigField("boolean", "FIREBASE_CONFIGURED", firebaseConfigured.toString())
    }

    signingConfigs {
        create("release") {
            // Supplied by CI or a local key.properties; see README § Release signing.
            // Absent locally, so `release` falls back to debug keys below and
            // `flutter build apk --release` still works for a smoke test.
            val keystorePath = System.getenv("MTAG_KEYSTORE_PATH")
            if (keystorePath != null) {
                storeFile = file(keystorePath)
                storePassword = System.getenv("MTAG_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("MTAG_KEY_ALIAS")
                keyPassword = System.getenv("MTAG_KEY_PASSWORD")
            }
        }
    }

    // Real product flavours, not a debug-only manifest override.
    //
    // The reason matters: the toll LAN is HTTP-only (`config.settings.lan` sets
    // SESSION_COOKIE_SECURE = False precisely because there is no TLS there), and
    // operators test with RELEASE builds on that LAN. Putting usesCleartextTraffic in the
    // debug source set only would leave a release LAN build unable to hold the session
    // cookie — login returns 200 and the next request is anonymous.
    //
    // So `dev` and `lan` carry cleartext in their own source sets, and `prod` does not and
    // cannot: there is no manifest in src/prod that permits it.
    flavorDimensions += "environment"

    productFlavors {
        create("dev") {
            dimension = "environment"
            applicationIdSuffix = ".dev"
            versionNameSuffix = "-dev"
        }
        create("lan") {
            dimension = "environment"
            applicationIdSuffix = ".lan"
            versionNameSuffix = "-lan"
        }
        create("prod") {
            dimension = "environment"
        }
    }

    buildFeatures {
        // Required for buildConfigField above; off by default since AGP 8.
        buildConfig = true
    }

    buildTypes {
        release {
            signingConfig = if (System.getenv("MTAG_KEYSTORE_PATH") != null) {
                signingConfigs.getByName("release")
            } else {
                // Debug keys, so a release build is testable without the real keystore.
                // A store upload with these is rejected, which is the desired failure —
                // silently shipping debug-signed would be worse.
                signingConfigs.getByName("debug")
            }
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

dependencies {
    // The desugaring runtime that `isCoreLibraryDesugaringEnabled` above needs. It ships the
    // backported java.time classes flutter_local_notifications calls on older Android.
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.5")
}

flutter {
    source = "../.."
}
