# ── Hopeland / HY820 PDA SDK (app/libs/*.jar, *.aar) ────────────────────────
#
# The bundled native libraries (libpda.so, libDeviceApi.so, libBarcodeAPI.so)
# resolve Java fields and methods BY NAME at runtime via JNI GetFieldID /
# GetMethodID. R8 keeps the *class* names (they declare native methods) but
# will happily rename their *members*, after which the lookup returns null and
# the JNI layer aborts the whole process — not a catchable Dart exception:
#
#   JNI DETECTED ERROR IN APPLICATION: fid == null
#       in call to GetObjectField
#       from void com.clouiotech.port.x3a.lib.Serial.setSpeed(int)
#
# That fired on every login, because ScanScreen.initState() opens the reader.
# R8 had renamed Serial.fileInputStream -> a and Serial.fileOutputStream -> b.
#
# Flutter's Gradle plugin force-enables minification for release builds
# (FlutterPlugin.kt: releaseBuildType.isMinifyEnabled = true) and auto-appends
# this file, so the SDK must be kept explicitly. The vendor's own PDAExample
# sample sidesteps the issue entirely with minifyEnabled false.

# Core PDA / RFID SDK (pdasdk_v3.45_20250317.jar)
-keep class com.pda.** { *; }
-keep class com.hopeland.** { *; }
-keep class com.clouiotech.** { *; }
-keep class com.port.** { *; }
-keep class com.util.** { *; }
-keep class cepri.** { *; }

# Barcode / scanner + device APIs (BarcodeAPI*.aar, DeviceAPI*.aar)
-keep class com.barcode.** { *; }
-keep class com.panling.deviceapi.** { *; }
-keep class com.dawn.decoderapijni.** { *; }
-keep class com.hsm.barcode.** { *; }
-keep class com.idata.scanner.** { *; }
-keep class com.mipha.barcode.** { *; }
-keep class com.zebra.** { *; }
-keep class com.custom.** { *; }

# The SDK jars reference optional/vendor-specific classes that are not all
# present; keeping the packages above surfaces them as missing-class warnings.
-dontwarn com.pda.**
-dontwarn com.hopeland.**
-dontwarn com.clouiotech.**
-dontwarn com.port.**
-dontwarn com.util.**
-dontwarn cepri.**
-dontwarn com.barcode.**
-dontwarn com.panling.**
-dontwarn com.dawn.**
-dontwarn com.hsm.**
-dontwarn com.idata.**
-dontwarn com.mipha.**
-dontwarn com.zebra.**
-dontwarn com.custom.**

# Belt and braces: any class declaring native methods keeps its members, since
# JNI binds them (and the fields they touch) by name.
-keepclasseswithmembernames,includedescriptorclasses class * {
    native <methods>;
}
