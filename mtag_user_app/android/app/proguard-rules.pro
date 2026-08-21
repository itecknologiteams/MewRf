# R8 rules.
#
# Flutter's own engine classes and the plugins' generated registrant are kept by the
# Flutter Gradle plugin's consumer rules, so this file only covers what R8 cannot see.

# drift/sqlite3: the native library is loaded reflectively by sqlite3_flutter_libs.
-keep class com.tekartik.** { *; }

# local_auth reaches AndroidX Biometric through reflection on some OEM builds.
-keep class androidx.biometric.** { *; }

# flutter_inappwebview registers JavaScript interfaces by name; R8 renaming them breaks
# the return-URL interception that the JazzCash checkout leg depends on.
-keep class com.pichillilorenzo.flutter_inappwebview_android.** { *; }

# Do NOT keep source file names or line numbers.
#
# Stack traces in a release build are obfuscated on purpose: this app handles balances and
# TIDs, and a readable trace in a crash report is a map of the data layer. Deobfuscate
# with the mapping.txt that the build produces instead.
-renamesourcefileattribute SourceFile
