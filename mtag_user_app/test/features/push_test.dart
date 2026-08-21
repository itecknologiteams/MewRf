import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/features/notifications/data/push_service.dart';
import 'package:mtag_user_app/features/notifications/presentation/push_controller.dart';

/// Push, in an environment with no Firebase — which is both the test VM and any build made
/// without a `google-services.json`.
void main() {
  group('PushService in an unconfigured environment', () {
    test('reports notConfigured instead of throwing', () async {
      // THE assertion behind the whole design. `Firebase.initializeApp()` throws on Android
      // when no config file was present at build time, and this call sits in the app's
      // startup path. A throw here kills `main` before the first frame — which produces an
      // app that installs cleanly and shows a black screen.
      //
      // That is not hypothetical: the prod flavour shipped exactly that failure once, from
      // a hard `throw` over a missing MTAG_CERT_PINS. Startup code that can fail must fail
      // into a STATE, not an exception.
      final service = PushService();
      await expectLater(service.initialise(), completes);
      expect(await service.initialise(), PushAvailability.notConfigured);
    });

    test('every accessor is safe to call when Firebase is absent', () async {
      final service = PushService();
      await service.initialise();

      // A UI that asks for a token before checking availability must not crash. Each of
      // these returns an empty answer rather than raising.
      expect(await service.registration(), isNull);
      expect(await service.initialMessage(), isNull);
      expect(await service.onTokenRefresh.isEmpty, isTrue);
      await expectLater(service.deleteToken(), completes);
      expect(await service.requestPermission(), PushAvailability.notConfigured);
    });

    test('initialising twice is idempotent, not a second failure', () async {
      // Called from both `main` and the controller; the second call must not undo the first
      // or re-throw.
      final service = PushService();
      final first = await service.initialise();
      final second = await service.initialise();
      expect(second, first);
    });
  });

  group('PushEvent maps the server payload', () {
    RemoteMessage message(Map<String, String> data) =>
        RemoteMessage(data: data);

    test('reads type and route from data, not from the display text', () {
      // `notification` is absent on a data-only send and is a LOCALISED display string;
      // deciding what to refresh from it would break the moment the wording changed.
      final event = PushEvent.fromMessage(
        message({
          'type': 'transaction',
          'transaction_type': 'toll_deduction',
          'account_id': '12',
          'route': '/activity?account=12',
        }),
      );

      expect(event.type, 'transaction');
      expect(event.route, '/activity?account=12');
      expect(event.affectsBalance, isTrue);
    });

    test('a missing or empty route is null, never an empty string', () {
      // go_router throws on an unmatched location, and '' matches nothing. A tap handler
      // that passed '' straight through would crash the app as it opened.
      expect(PushEvent.fromMessage(message({'type': 'transaction'})).route, isNull);
      expect(
        PushEvent.fromMessage(message({'type': 'transaction', 'route': ''})).route,
        isNull,
      );
    });

    test('a failed top-up counts as balance-affecting', () {
      // It resolves a PENDING top-up the user is watching, so the wallet and the top-up
      // history are both stale even though no money moved.
      final event = PushEvent.fromMessage(
        message({'type': 'topup_failed', 'route': '/topup?account=12'}),
      );
      expect(event.affectsBalance, isTrue);
    });

    test('an unknown type from a newer backend is inert, not a crash', () {
      // The server can grow new notification types before the app knows them. An unknown
      // one must not trigger a refresh storm or an exception.
      final event = PushEvent.fromMessage(message({'type': 'tag_expiring_soon'}));
      expect(event.type, 'tag_expiring_soon');
      expect(event.affectsBalance, isFalse);
      expect(event.route, isNull);
    });
  });

  group('PushState tells the four failure modes apart', () {
    test('isWorking requires the user, the device AND the server', () {
      // Three independent things can each silence push: the user declining, the build
      // having no Firebase config, and the BACKEND having no service-account credentials.
      // A single boolean would let the app claim alerts are on when the server cannot send
      // any — the LAN deployment's normal state.
      const allGood = PushState(
        availability: PushAvailability.ready,
        optedIn: true,
        serverCanSend: true,
      );
      expect(allGood.isWorking, isTrue);

      expect(
        const PushState(
          availability: PushAvailability.ready,
          optedIn: true,
        ).isWorking,
        isFalse,
        reason: 'a server with no FCM credentials cannot deliver to a valid token',
      );
      expect(
        const PushState(
          availability: PushAvailability.ready,
          optedIn: false,
          serverCanSend: true,
        ).isWorking,
        isFalse,
        reason: "the user's own choice must win",
      );
      expect(
        const PushState(
          availability: PushAvailability.notConfigured,
          optedIn: true,
          serverCanSend: true,
        ).isWorking,
        isFalse,
      );
    });
  });
}
