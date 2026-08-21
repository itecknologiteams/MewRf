pluginManagement {
    val flutterSdkPath =
        run {
            val properties = java.util.Properties()
            file("local.properties").inputStream().use { properties.load(it) }
            val flutterSdkPath = properties.getProperty("flutter.sdk")
            require(flutterSdkPath != null) { "flutter.sdk not set in local.properties" }
            flutterSdkPath
        }

    includeBuild("$flutterSdkPath/packages/flutter_tools/gradle")

    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

plugins {
    id("dev.flutter.flutter-plugin-loader") version "1.0.0"
    id("com.android.application") version "9.0.1" apply false
    id("org.jetbrains.kotlin.android") version "2.3.20" apply false
    // DECLARED here, APPLIED conditionally in app/build.gradle.kts.
    //
    // `apply false` is the whole trick: the plugin is on the classpath and ready, but it
    // does not run, so a checkout with no google-services.json still builds. Applying it
    // unconditionally fails the build outright with "File google-services.json is
    // missing" — which would mean nobody could build the app until Firebase was set up.
    id("com.google.gms.google-services") version "4.4.4" apply false
}

include(":app")
