import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// The Android notification channel id, checked against the server that sends it.
///
/// This exists because of a failure mode with no symptom. Every FCM message the backend
/// sends names a channel explicitly in its `android.notification` block, and a message that
/// NAMES a channel ignores the manifest's default. Android 8+ then discards any notification
/// whose channel does not exist on the device — silently. No exception, nothing in logcat,
/// nothing on screen.
///
/// So a one-word difference between two files in two different languages produces a push
/// system that is correct end to end, registers tokens, reports `push_available: true`, and
/// delivers nothing. Nothing else in either test suite compares them, because neither side
/// is wrong on its own.
void main() {
  group('the app and the server agree on the channel id', () {
    test('strings.xml matches the channel_id in services.py', () {
      final strings = File(
        'android/app/src/main/res/values/strings.xml',
      ).readAsStringSync();
      final service = File(
        '../mtag_backend/apps/notifications/services.py',
      );

      // Skipped rather than failed when the backend is not checked out beside the app: this
      // is a cross-repo invariant, and a missing sibling is not a broken app.
      if (!service.existsSync()) {
        markTestSkipped('backend not present at ../mtag_backend');
        return;
      }

      final declared = RegExp(
        '<string name="notification_channel_money"[^>]*>([^<]+)</string>',
      ).firstMatch(strings)?.group(1)?.trim();

      final sent = RegExp(
        r"'channel_id':\s*'([^']+)'",
      ).firstMatch(service.readAsStringSync())?.group(1);

      expect(declared, isNotNull, reason: 'channel string missing from strings.xml');
      expect(sent, isNotNull, reason: 'channel_id missing from services.py');
      expect(
        declared,
        sent,
        reason:
            'the app declares "$declared" but the server sends "$sent" — every '
            'notification would be discarded by Android without any error',
      );
    });

    test('the manifest points at that string and names an icon', () {
      final manifest = File(
        'android/app/src/main/AndroidManifest.xml',
      ).readAsStringSync();

      // Without the default channel meta-data, a message that does NOT name a channel is
      // dropped for the same reason as above.
      expect(
        manifest.contains(
          'com.google.firebase.messaging.default_notification_channel_id',
        ),
        isTrue,
      );
      expect(manifest.contains('@string/notification_channel_money'), isTrue);

      // Android tints the small icon and discards colour, so a full-colour launcher icon
      // renders as a white blob. A dedicated monochrome asset is the only thing that
      // survives.
      expect(
        manifest.contains(
          'com.google.firebase.messaging.default_notification_icon',
        ),
        isTrue,
      );
      expect(
        File('android/app/src/main/res/drawable/ic_notification.xml').existsSync(),
        isTrue,
      );
    });

    test('POST_NOTIFICATIONS is declared for Android 13+', () {
      // From API 33 the permission is a runtime grant. Without the declaration the request
      // is auto-denied and every push is dropped, again with no error.
      final manifest = File(
        'android/app/src/main/AndroidManifest.xml',
      ).readAsStringSync();
      expect(
        manifest.contains('android.permission.POST_NOTIFICATIONS'),
        isTrue,
      );
    });
  });
}
