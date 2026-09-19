import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:mtag_user_app/app.dart';
import 'package:mtag_user_app/core/cache/cache_database.dart';
import 'package:mtag_user_app/core/network/api_client.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/core/security/screen_security.dart';
import 'package:mtag_user_app/features/notifications/data/foreground_notifications.dart';
import 'package:path_provider/path_provider.dart';

/// Handles a push that arrives while the app is backgrounded or terminated.
///
/// Runs in its OWN isolate with no access to anything `main` set up — no Riverpod, no
/// cookie jar, no cache — which is why it does nothing but return. It has to exist anyway:
/// `FirebaseMessaging.onBackgroundMessage` must be registered before any message can
/// arrive, and a DATA-ONLY message on Android is dropped without it.
///
/// Must be a top-level function annotated `@pragma('vm:entry-point')`, or tree-shaking
/// removes it from a release build and background delivery silently stops working in
/// release only — the worst possible place for it to break.
///
/// Notification-carrying messages (which is all the server currently sends) are rendered by
/// the system tray without this being involved. When the app is next opened, the wallet is
/// refetched anyway, so there is no state to reconcile here.
@pragma('vm:entry-point')
Future<void> _onBackgroundMessage(RemoteMessage message) async {
  // No side effects on purpose. Writing to the cache from here would race the main
  // isolate's drift connection over the same file.
  debugPrint('Push (background): ${message.data['type']}');
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // EVERY startup step is inside this guard, and the reason is a scar rather than a
  // principle. Twice now this app has shipped a `main` that could throw, and both times the
  // result was identical and undiagnosable from the outside: the process starts, the window
  // gains focus, the NATIVE splash stays up forever, and no error reaches the user because
  // Flutter never painted a frame to put one on.
  //
  //   * the prod flavour threw on a missing MTAG_CERT_PINS  -> black screen
  //   * the cookie store threw BAD_DECRYPT after a restore  -> stuck on the splash
  //
  // The second is the worse of the two: it needs no mistake by anyone. Restoring a backup
  // onto a new phone is the ordinary way people change handsets, and it leaves
  // flutter_secure_storage holding ciphertext whose Keystore key was never backed up.
  //
  // So a startup failure now produces a SCREEN — one that says what happened and offers the
  // one action that fixes it — instead of an app that has to be force-stopped and cleared
  // by a user who has no reason to know that is even possible.
  try {
    // Both of these are opened BEFORE the first frame, and both have to be.
    //
    // The cookie jar IS the session — there is no token in memory to fall back on —
    // so a first frame painted before the jar is on disk would decide the user is
    // signed out and route them to login while a perfectly good 7-day session sat
    // unread on disk. The cache is opened here for the same reason: the splash screen
    // paints real content from it, and a late-arriving database means a flash of empty
    // state on every cold start.
    final apiClient = await ApiClient.create();
    final cache = CacheDatabase();

    // FLAG_SECURE is installed once, globally, and the top-up screens raise it. Doing
    // it here rather than per-screen means there is no window during a route
    // transition where a balance is screenshottable.
    await ScreenSecurity.instance.initialise();

    // Push, if this build was given a Firebase config.
    //
    // Kept in its own try even inside the outer one: push is an enhancement, and a Firebase
    // failure must degrade to "no notifications" rather than to the recovery screen below.
    // `initializeApp` throws when no google-services.json was present at build time, which
    // is a supported way to build this app.
    //
    // The background handler is registered HERE, before runApp: FCM requires it to be in
    // place before any message can be delivered.
    try {
      if (Firebase.apps.isEmpty) {
        await Firebase.initializeApp();
      }
      FirebaseMessaging.onBackgroundMessage(_onBackgroundMessage);

      // Draws notifications that arrive while the app is OPEN.
      //
      // Android does not display an FCM notification message to a foreground app — it hands
      // it to `onMessage` and draws nothing. Without this, a push delivered while the user
      // is looking at the app succeeds everywhere it is observed (FCM returns 200, the
      // server logs a delivery) and appears nowhere, which is indistinguishable from push
      // being broken.
      //
      // Started here rather than from a screen because the two moments it matters most are
      // onboarding, before any session exists, and the dashboard after one does.
      await ForegroundNotifications.instance.start();
    } on Object catch (error) {
      debugPrint('Push unavailable — continuing without it: $error');
    }

    runApp(
      ProviderScope(
        overrides: [
          apiClientProvider.overrideWithValue(apiClient),
          cacheDatabaseProvider.overrideWithValue(cache),
        ],
        child: const MTagApp(),
      ),
    );
  } on Object catch (error, stack) {
    debugPrint('Startup failed: $error\n$stack');
    runApp(_StartupFailureApp(error: error));
  }
}

/// Shown only when startup itself failed.
///
/// Deliberately built from bare Flutter widgets and hard-coded strings: the design system,
/// the localisations and the providers all live behind the initialisation that just failed,
/// so anything that reaches for them could throw again and leave the user back on a frozen
/// splash. An ugly screen that renders beats a beautiful one that might not.
class _StartupFailureApp extends StatelessWidget {
  const _StartupFailureApp({required this.error});

  final Object error;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: Scaffold(
        backgroundColor: const Color(0xFF050505),
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(32),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Icon(
                      Icons.refresh_rounded,
                      color: Color(0xFFFF8500),
                      size: 48,
                    ),
                    const SizedBox(height: 24),
                    const Text(
                      "ME-Tag couldn't start",
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 22,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 12),
                    const Text(
                      'This usually happens after restoring a backup onto a new phone. '
                      'Resetting clears the saved login on this device — your balance, '
                      'tags and trips are safe on your account.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Color(0xFFA3A3A3), height: 1.5),
                    ),
                    const SizedBox(height: 28),
                    _ResetButton(),
                    const SizedBox(height: 16),
                    // The raw error, small and last. Useless to most users and the only
                    // thing that helps whoever they eventually show the phone to.
                    Text(
                      '$error',
                      textAlign: TextAlign.center,
                      maxLines: 4,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Color(0xFF6B6B6B),
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _ResetButton extends StatefulWidget {
  @override
  State<_ResetButton> createState() => _ResetButtonState();
}

class _ResetButtonState extends State<_ResetButton> {
  bool _busy = false;
  String? _message;

  Future<void> _reset() async {
    setState(() {
      _busy = true;
      _message = null;
    });

    // Wipes both halves of the problem: the secure store holding undecryptable ciphertext,
    // and the cookie jar it vouches for. Neither holds anything that is not recoverable by
    // signing in again.
    try {
      await const FlutterSecureStorage(
        aOptions: AndroidOptions(resetOnError: true),
      ).deleteAll();
    } on Object {
      // A Keystore too wedged to delete from still gets the directory wipe below.
    }
    try {
      final support = await getApplicationSupportDirectory();
      final jar = Directory('${support.path}/mtag_cookies');
      if (jar.existsSync()) jar.deleteSync(recursive: true);
    } on Object {
      // Nothing further to try.
    }

    if (!mounted) return;
    setState(() {
      _busy = false;
      // The process cannot restart itself, and a half-initialised app is worse than a
      // closed one — so the honest instruction is to reopen it.
      _message = 'Reset. Close ME-Tag completely and open it again.';
    });
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        FilledButton(
          onPressed: _busy ? null : _reset,
          style: FilledButton.styleFrom(
            backgroundColor: const Color(0xFFFF8500),
            foregroundColor: Colors.black,
            minimumSize: const Size.fromHeight(52),
          ),
          child: Text(_busy ? 'Resetting…' : 'Reset and restart'),
        ),
        if (_message != null) ...[
          const SizedBox(height: 14),
          Text(
            _message!,
            textAlign: TextAlign.center,
            style: const TextStyle(color: Color(0xFF4ADE80), fontSize: 13),
          ),
        ],
      ],
    );
  }
}
