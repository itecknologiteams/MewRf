package com.mtag.mtag_user_app

import android.view.WindowManager
import io.flutter.embedding.android.FlutterFragmentActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * Hosts the Flutter UI and implements the screen-security channel.
 *
 * `FLAG_SECURE` is the only mechanism Android offers here, and it does three things at
 * once: blocks screenshots, blocks screen recording, and blanks the app's thumbnail in
 * the recents list. The last one matters most for this app — a tag holder's balance and
 * TID sitting in the recents preview is visible to anyone who picks up the phone.
 *
 * Raised per screen by [ScreenSecurity] rather than for the whole app, because a
 * permanently secure window also blocks legitimate screenshots of the trip history that
 * users take to send to their employer.
 *
 * There is no iOS counterpart. iOS permits screenshots unconditionally and offers no
 * equivalent flag, so the Dart side no-ops there rather than pretending parity.
 *
 * ## FlutterFragmentActivity, not FlutterActivity
 *
 * `local_auth` shows the system BiometricPrompt, which is an AndroidX Fragment and can only
 * be hosted by a FragmentActivity. On a plain FlutterActivity every biometric call fails
 * with `no_fragment_activity` — the prompt simply never appears, and the failure surfaces as
 * "biometrics unavailable" rather than as a misconfiguration. This is a required base class
 * for the feature, not a preference.
 */
class MainActivity : FlutterFragmentActivity() {
    private companion object {
        const val CHANNEL = "mtag/screen_security"
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "initialise" -> result.success(null)

                    "enable" -> {
                        // runOnUiThread: window flags must be set on the UI thread, and a
                        // MethodChannel handler is not guaranteed to be on it.
                        runOnUiThread {
                            window.setFlags(
                                WindowManager.LayoutParams.FLAG_SECURE,
                                WindowManager.LayoutParams.FLAG_SECURE,
                            )
                        }
                        result.success(null)
                    }

                    "disable" -> {
                        runOnUiThread {
                            window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
                        }
                        result.success(null)
                    }

                    else -> result.notImplemented()
                }
            }
    }
}
