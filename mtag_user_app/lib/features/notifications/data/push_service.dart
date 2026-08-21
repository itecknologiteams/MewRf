import 'dart:async';
import 'dart:io' show Platform;

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:mtag_user_app/core/env/app_env.dart';

/// Why push is or is not available.
///
/// Four distinct states, because "notifications are off" has four different fixes and
/// collapsing them into one boolean is how a user ends up toggling a switch that can never
/// work. Only [PushAvailability.ready] means a token can be obtained.
enum PushAvailability {
  /// A token is obtainable and permission is granted.
  ready,

  /// The build has no Firebase config, so there is nothing to register with. A BUILD
  /// mistake, not a user choice — the UI says so rather than offering a switch.
  notConfigured,

  /// The user declined, or has not been asked. Recoverable, and theirs to decide.
  permissionDenied,

  /// Google Play services missing or too old, an emulator without them, or an FCM
  /// outage. Nothing the app or the user can do.
  unsupported,
}

class PushRegistration {
  const PushRegistration({required this.token, required this.platform});

  final String token;

  /// Matches the server's `DevicePlatform` choices exactly: `android` / `ios`.
  final String platform;
}

/// The FCM plumbing, and nothing above it.
///
/// Deliberately free of Riverpod, routing and repositories so it can be faked in a test
/// without a Firebase binary channel — every test in this app runs on the Dart VM, where
/// there is no Firebase at all.
///
/// ## Initialising is allowed to fail
///
/// `Firebase.initializeApp()` THROWS on Android when no `google-services.json` was present
/// at build time, because there are no default options to read. That is a supported state
/// here: the Gradle plugin is applied conditionally, so a checkout with no Firebase project
/// still builds and runs. Every entry point below therefore tolerates an uninitialised
/// Firebase and reports [PushAvailability.notConfigured] instead of throwing into `main`.
///
/// That guard is not hypothetical caution. The prod flavour already shipped once with a
/// hard `throw` in its startup path (a missing `MTAG_CERT_PINS`), and the result was an app
/// that installed cleanly and showed a black screen — `main` had died before the first
/// frame. Startup code that can fail must fail into a STATE, not an exception.
class PushService {
  PushService({FirebaseMessaging? messaging}) : _injected = messaging;

  final FirebaseMessaging? _injected;

  bool _initialised = false;
  bool _firebaseReady = false;

  FirebaseMessaging? get _messaging {
    if (_injected != null) return _injected;
    if (!_firebaseReady) return null;
    return FirebaseMessaging.instance;
  }

  /// Brings Firebase up if it can be brought up. Safe to call more than once.
  Future<PushAvailability> initialise() async {
    if (_injected != null) {
      _initialised = true;
      _firebaseReady = true;
      return PushAvailability.ready;
    }

    if (_initialised) {
      return _firebaseReady
          ? PushAvailability.ready
          : PushAvailability.notConfigured;
    }
    _initialised = true;

    try {
      // An app already initialised by a background isolate must not be initialised twice —
      // `initializeApp` throws `duplicate-app` for that, which is success, not failure.
      if (Firebase.apps.isEmpty) {
        await Firebase.initializeApp();
      }
      _firebaseReady = true;
      return PushAvailability.ready;
    } on FirebaseException catch (error) {
      if (error.code == 'duplicate-app') {
        _firebaseReady = true;
        return PushAvailability.ready;
      }
      debugPrint('Push: Firebase unavailable (${error.code}) — push disabled.');
      return PushAvailability.notConfigured;
    } on Object catch (error) {
      // A MissingPluginException on an unsupported platform lands here, as does the
      // "No Firebase App has been created" state on a build with no config file.
      debugPrint('Push: Firebase init failed ($error) — push disabled.');
      return PushAvailability.notConfigured;
    }
  }

  /// Asks for permission, and reports what the user decided.
  ///
  /// Called when the user opts in, not on first launch: a permission sheet shown before the
  /// app has said what the notifications are for is the one most reliably denied, and on
  /// Android a denial is permanent enough that the app can never ask again.
  Future<PushAvailability> requestPermission() async {
    final messaging = _messaging;
    if (messaging == null) return PushAvailability.notConfigured;

    try {
      final settings = await messaging.requestPermission();
      return switch (settings.authorizationStatus) {
        AuthorizationStatus.authorized ||
        // iOS provisional authorisation: notifications arrive quietly in Notification
        // Centre without a prompt. Treated as ready because delivery genuinely works.
        AuthorizationStatus.provisional => PushAvailability.ready,
        AuthorizationStatus.denied => PushAvailability.permissionDenied,
        AuthorizationStatus.notDetermined => PushAvailability.permissionDenied,
      };
    } on Object catch (error) {
      debugPrint('Push: permission request failed ($error).');
      return PushAvailability.unsupported;
    }
  }

  /// The current device token, or null if there is none to be had.
  Future<PushRegistration?> registration() async {
    final messaging = _messaging;
    if (messaging == null) return null;

    try {
      final token = await messaging.getToken();
      if (token == null || token.isEmpty) {
        debugPrint('Push: getToken returned nothing.');
        return null;
      }
      // Opt-in only — see AppEnv.logPushToken for why a token is not an ordinary log line.
      if (AppEnv.logPushToken) {
        debugPrint('Push: FCM token = $token');
      }
      return PushRegistration(token: token, platform: _platformName());
    } on Object catch (error) {
      // Thrown on a device with no Play services, and on an iOS simulator, which has no
      // APNS token at all. Neither is an error worth showing a user.
      debugPrint('Push: token unavailable ($error).');
      return null;
    }
  }

  /// Fires when FCM rotates the token.
  ///
  /// Rotation is routine — app restore, a data clear, a long idle period — and a stale
  /// token is not an error the server can detect: sends simply stop arriving. Re-registering
  /// on this stream is what keeps notifications working over months.
  Stream<PushRegistration> get onTokenRefresh {
    final messaging = _messaging;
    if (messaging == null) return const Stream<PushRegistration>.empty();
    return messaging.onTokenRefresh
        .where((token) => token.isNotEmpty)
        .map((token) => PushRegistration(token: token, platform: _platformName()));
  }

  /// Messages arriving while the app is in the foreground.
  Stream<RemoteMessage> get onForegroundMessage => FirebaseMessaging.onMessage;

  /// A notification the user TAPPED, which resumed the app from the background.
  Stream<RemoteMessage> get onMessageOpened =>
      FirebaseMessaging.onMessageOpenedApp;

  /// The notification that launched the app from a terminated state, if any.
  ///
  /// Separate from [onMessageOpened] because it is a one-shot value rather than a stream:
  /// the tap happened before any listener existed, so it has to be pulled, not awaited.
  Future<RemoteMessage?> initialMessage() async {
    final messaging = _messaging;
    if (messaging == null) return null;
    try {
      return await messaging.getInitialMessage();
    } on Object {
      return null;
    }
  }

  /// Drops the local token so a signed-out device stops receiving the last user's alerts.
  ///
  /// Belt and braces with the server-side unregister: deleting the row stops sends, and
  /// deleting the token means even an in-flight message has nowhere to land.
  Future<void> deleteToken() async {
    final messaging = _messaging;
    if (messaging == null) return;
    try {
      await messaging.deleteToken();
    } on Object catch (error) {
      debugPrint('Push: token delete failed ($error).');
    }
  }

  static String _platformName() => Platform.isIOS ? 'ios' : 'android';
}
