# m-tag Scanner (Flutter, Android 9 / HY820)

Handheld scanner app for the HY820 (Hopeland) UHF reader. Features:

- **Login** (admin) — cookie-based auth against the m-tag backend.
- **Server Configuration** screen — set the backend base URL (LAN IP).
- **Scan** screen — start/stop inventory, live EPC + TID list with a **count**,
  and **Upload** in two modes:
  - **Direct** → `POST /vehicles/tags/bulk/` (status `deactivated`, auto serial)
  - **Buffer** → `POST /vehicles/tags/scan/` (bulk-tags web app shows it live)
- **Manual add** field on the Scan screen — test the whole login → collect →
  upload flow **without** the SDK/hardware.

This project is **already set up**: `lib/` source, `pubspec.yaml`, the generated
`android/` platform folder, the native bridge placed at
`android/app/src/main/kotlin/com/example/mtag_scanner/MainActivity.kt`, and the
manifest configured (INTERNET + cleartext HTTP for Android 9). `flutter analyze`
passes clean. A copy of the bridge is also kept in `android_bridge/MainActivity.kt`.

## Build steps

```bash
flutter pub get
flutter build apk --release
#  output: build/app/outputs/flutter-apk/app-release.apk
```

> If you ever regenerate platform folders (`flutter create .`), re-copy
> `android_bridge/MainActivity.kt` into
> `android/app/src/main/kotlin/com/example/mtag_scanner/MainActivity.kt` and
> re-add `android:usesCleartextTraffic="true"` + the INTERNET permission to the
> manifest.

## Already configured

- `AndroidManifest.xml`: `INTERNET` permission + `android:usesCleartextTraffic="true"`
  (backend is plain HTTP; Android 9 blocks cleartext by default).
- For a fresh build the default `minSdk` installs fine on Android 9 (API 28);
  set `minSdkVersion 28` in `android/app/build.gradle` if you want to target 9+.

## Hopeland SDK integration (required for real scanning)

Without the Hopeland Android SDK the app runs and the **manual add** + upload
work, but the reader shows "unavailable". To enable hardware scanning:

1. Add the Hopeland Android SDK (`.aar`/`.jar`) to `android/app/libs/` and
   reference it in `android/app/build.gradle` dependencies.
2. Fill the `TODO(SDK)` blocks in `MainActivity.kt`:
   - `connectReader()` — init the reader + enable **extended TID read**
     (analog of the Python `WO_RFIDReadExtended` with `TID`), register the tag
     callback so it calls `emitTag(tid, epc)`.
   - `startInventory()` / `stopInventory()` — start/stop continuous read.
   - The SDK's tag callback (analog of Python `OutputTags` → `_EPC` / `_TID`)
     must call `emitTag(tag.tid, tag.epc)`.

The Dart side already streams those tags into the list + count.

## Notes

- Set the server URL on first run (Settings ⚙ on the login screen), e.g.
  `http://192.168.78.249:8000/api/v1`. Device + backend must share the network.
- Login uses an **admin** account; the session cookie authorises the upload
  endpoints.
