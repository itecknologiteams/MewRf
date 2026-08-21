import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// Draws a notification for a push that arrives while the app is OPEN.
///
/// ## Why this is needed at all
///
/// Android does not display an FCM notification message while the target app is in the
/// foreground. It hands the message to `FirebaseMessaging.onMessage` and draws nothing, on
/// the reasoning that a visible app should show its own news. The consequence, if nobody
/// does, is a push that succeeds at every observable layer and appears nowhere: FCM returns
/// 200, the server logs a delivery, and the user watching the screen sees no notification
/// and concludes push is broken.
///
/// That is exactly what happened with the OTP code — it was delivered to a foreground app
/// during onboarding, where the only listener in the app was mounted behind authentication.
///
/// ## Why it lives outside the widget tree
///
/// Started from `main()`, not from a screen. The two moments a push matters most are
/// onboarding (before any session exists) and the dashboard (after one does), and a listener
/// owned by either would miss the other.
///
/// ## Channel id
///
/// [_channelId] MUST match the `channel_id` the server puts in every message
/// (`apps/notifications/services.py`) and the manifest's default channel. Android silently
/// discards a notification whose channel does not exist, so three identifiers that merely
/// look alike produce a fully wired push system that delivers nothing.
class ForegroundNotifications {
  ForegroundNotifications._();

  static final ForegroundNotifications instance = ForegroundNotifications._();

  static const _channelId = 'mtag_transactions';
  static const _channelName = 'Payments and tolls';
  static const _channelDescription =
      'Top-ups, toll charges, refunds and verification codes.';

  final _plugin = FlutterLocalNotificationsPlugin();
  StreamSubscription<RemoteMessage>? _subscription;
  bool _ready = false;

  /// Safe to call when Firebase is absent, and safe to call twice.
  ///
  /// Never throws: this runs in `main()` before the first frame, and a throw there is an app
  /// that shows the native splash forever rather than an error anyone can act on.
  Future<void> start() async {
    if (_subscription != null) return;

    try {
      await _initialise();
      _subscription = FirebaseMessaging.onMessage.listen(_show);
    } on Object catch (error) {
      debugPrint('Foreground notifications unavailable: $error');
    }
  }

  Future<void> _initialise() async {
    const settings = InitializationSettings(
      // The small icon Android tints; a full-colour launcher icon renders as a white blob.
      android: AndroidInitializationSettings('@drawable/ic_notification'),
      // Permission is requested by the push flow at the point the user is waiting for a
      // code, so it is not asked for again here.
      iOS: DarwinInitializationSettings(
        requestAlertPermission: false,
        requestBadgePermission: false,
        requestSoundPermission: false,
      ),
    );
    await _plugin.initialize(settings: settings);

    // Created explicitly rather than left to first use: the channel must exist before a
    // message can land, and creating it here means its name and description are ours rather
    // than the SDK's defaults.
    final android = _plugin
        .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin
        >();
    await android?.createNotificationChannel(
      const AndroidNotificationChannel(
        _channelId,
        _channelName,
        description: _channelDescription,
        importance: Importance.high,
      ),
    );

    _ready = true;
  }

  void _show(RemoteMessage message) {
    if (!_ready) return;

    final notification = message.notification;
    // Data-only messages carry nothing to display. They are still delivered to the app's
    // own listeners — the OTP auto-fill reads one — so silence here is correct, not a
    // dropped message.
    if (notification == null) return;

    unawaited(
      _plugin
          .show(
            // Keyed by type so a second toll charge replaces the first rather than
            // stacking, but an OTP never replaces a balance alert.
            id: message.data['type'].hashCode,
            title: notification.title,
            body: notification.body,
            notificationDetails: const NotificationDetails(
              android: AndroidNotificationDetails(
                _channelId,
                _channelName,
                channelDescription: _channelDescription,
                importance: Importance.high,
                priority: Priority.high,
              ),
              iOS: DarwinNotificationDetails(),
            ),
            // Carried through so a tap can be routed the same way a background tap is.
            payload: message.data['route']?.toString(),
          )
          .catchError((Object error) {
            debugPrint('Could not show foreground notification: $error');
          }),
    );
  }

  Future<void> dispose() async {
    await _subscription?.cancel();
    _subscription = null;
  }
}
