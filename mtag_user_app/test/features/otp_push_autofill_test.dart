import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/core/data/auth_repository.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/features/onboarding/presentation/otp_controller.dart';

/// Auto-filling the OTP from a push.
///
/// This exists because of a failure that reported success at every layer. FCM accepted the
/// message, the server logged a delivery, and nothing appeared on the phone — because on
/// Android a NOTIFICATION message arriving while the app is in the FOREGROUND is not drawn
/// in the system tray; it is handed to `FirebaseMessaging.onMessage`. The app's only
/// foreground listener lived in `AppShell`, which is mounted inside the authenticated shell,
/// and onboarding happens before there is a session. So the code was delivered to a listener
/// that did not exist.
///
/// The handler is unit-testable on purpose: the stream behind it is a static platform
/// channel that cannot be exercised on the Dart VM, so the message-handling logic is
/// separated from the subscription that carries it.
void main() {
  late ProviderContainer container;
  late OtpFlowController controller;

  setUp(() {
    container = ProviderContainer();
    addTearDown(container.dispose);
    controller = container.read(otpFlowControllerProvider.notifier)
      ..setPhone('03001112233');
  });

  RemoteMessage push(Map<String, String> data, {DateTime? sentTime}) =>
      RemoteMessage(data: data, sentTime: sentTime);

  /// A controller wired to a fake repository, for the cases where the push IS accepted.
  ///
  /// The fill itself cannot be observed directly: `onPushedCode` calls `verify()` straight
  /// after setting the code, and a failed verify clears it again. So acceptance is asserted
  /// through what actually reached the server.
  ({OtpFlowController controller, _FakeAuth auth}) accepting(OtpFlowState state) {
    final auth = _FakeAuth();
    final scoped = ProviderContainer(
      overrides: [authRepositoryProvider.overrideWithValue(auth)],
    );
    addTearDown(scoped.dispose);
    final c = scoped.read(otpFlowControllerProvider.notifier)
      ..state = state
      ..requestedAtForTest = DateTime.now();
    return (controller: c, auth: auth);
  }

  /// Puts the flow on the code step without touching the network.
  void onCodeStep() {
    controller.state = const OtpFlowState(
      step: OtpStep.code,
      phone: '03001112233',
    );
  }

  test('a pushed code fills the boxes and verifies immediately', () async {
    // The point of the feature: the user does not retype a code their own phone just
    // received. Asserted through the OUTCOME rather than the intermediate `code` value,
    // because auto-verify runs straight after the fill and, on success, moves the flow to
    // the password step — reading `code` afterwards would be racing the thing under test.
    final fake = _FakeAuth();
    final scoped = ProviderContainer(
      overrides: [authRepositoryProvider.overrideWithValue(fake)],
    );
    addTearDown(scoped.dispose);

    final scopedController = scoped.read(otpFlowControllerProvider.notifier)
      ..state = const OtpFlowState(step: OtpStep.code, phone: '03001112233')
      ..onPushedCode(push({'type': 'otp', 'code': '4821'}));

    // Let the verify future settle.
    await Future<void>.delayed(Duration.zero);

    expect(fake.verifiedCode, '4821', reason: 'the pushed code must be what is verified');
    expect(scoped.read(otpFlowControllerProvider).step, OtpStep.password);
    expect(scopedController.state.token, 'set-password-token');
  });

  test('ignores a push that is not an OTP', () {
    onCodeStep();
    // A toll charge landing mid-onboarding must not be typed into the code boxes.
    controller.onPushedCode(
      push({'type': 'transaction', 'code': '9999'}),
    );
    expect(container.read(otpFlowControllerProvider).code, isEmpty);
  });

  test('ignores an OTP push with no code, which is the PRODUCTION shape', () {
    onCodeStep();
    // Only the dev delivery path includes `code`. On a real server the push carries just
    // the notification, the user reads it and types it, and this handler must sit still
    // rather than clearing or half-filling the boxes.
    controller.onPushedCode(push({'type': 'otp'}));
    expect(container.read(otpFlowControllerProvider).code, isEmpty);
  });

  test('ignores a code of the wrong length', () {
    onCodeStep();
    // A malformed payload must not trigger a verify that is guaranteed to fail and burn
    // one of the five attempts the account gets.
    controller
      ..onPushedCode(push({'type': 'otp', 'code': '48'}))
      ..onPushedCode(push({'type': 'otp', 'code': '48210'}));
    expect(container.read(otpFlowControllerProvider).code, isEmpty);
  });

  test('ignores a push once the flow has moved past the code step', () {
    // A late push must not overwrite the password screen's state with a spent code.
    controller
      ..state = const OtpFlowState(
        step: OtpStep.password,
        phone: '03001112233',
        token: 'set-password-token',
      )
      ..onPushedCode(push({'type': 'otp', 'code': '4821'}));
    expect(container.read(otpFlowControllerProvider).code, isEmpty);
    expect(container.read(otpFlowControllerProvider).step, OtpStep.password);
  });

  group('stale codes', () {
    test('a code sent long before this request is ignored', () {
      // Observed in production logs: a verify fired 176ms after a fresh request, because
      // FCM redelivered a queued message from a previous session when the app reconnected.
      // The old code was auto-filled and submitted, spending one of the five attempts the
      // account gets — and the resulting failure ate into the OTP throttle, so the user was
      // rate-limited for a code they never typed.
      controller
        ..state = const OtpFlowState(step: OtpStep.code, phone: '03001112233')
        ..requestedAtForTest = DateTime.now()
        ..onPushedCode(
          push(
            {'type': 'otp', 'code': '4821'},
            sentTime: DateTime.now().subtract(const Duration(hours: 3)),
          ),
        );

      expect(container.read(otpFlowControllerProvider).code, isEmpty);
    });

    test('a code sent moments before the request still counts', () async {
      // Clock slack. `sentTime` is FCM's clock and `_requestedAt` is the device's, so a
      // small negative difference is skew, not staleness — rejecting it would break the
      // feature on any phone whose clock runs slightly fast.
      final f = accepting(
        const OtpFlowState(step: OtpStep.code, phone: '03001112233'),
      );
      f.controller.onPushedCode(
        push(
          {'type': 'otp', 'code': '4821'},
          sentTime: DateTime.now().subtract(const Duration(seconds: 2)),
        ),
      );
      await Future<void>.delayed(Duration.zero);
      expect(f.auth.verifiedCode, '4821');
    });

    test('a push with no sentTime is still accepted', () async {
      // Not every message carries one. Refusing those would disable auto-fill entirely on
      // whichever platform or version omits it, for a guard that is a safeguard rather
      // than a security boundary.
      final f = accepting(
        const OtpFlowState(step: OtpStep.code, phone: '03001112233'),
      );
      f.controller.onPushedCode(push({'type': 'otp', 'code': '4821'}));
      await Future<void>.delayed(Duration.zero);
      expect(f.auth.verifiedCode, '4821');
    });
  });

  group('purpose', () {
    test('a reset code is not auto-filled into a setup flow', () {
      // The server derives the token's signing salt from the purpose, so a cross-purpose
      // code would be refused at verify and read to the user as "that code is not correct".
      controller
        ..state = const OtpFlowState(
          step: OtpStep.code,
          phone: '03001112233',
        )
        ..requestedAtForTest = DateTime.now()
        ..onPushedCode(
          push({'type': 'otp', 'code': '4821', 'purpose': 'password_reset'}),
        );

      expect(container.read(otpFlowControllerProvider).code, isEmpty);
    });

    test('a matching purpose is accepted', () async {
      final f = accepting(
        const OtpFlowState(
          step: OtpStep.code,
          phone: '03001112233',
          purpose: OtpPurpose.passwordReset,
        ),
      );
      f.controller.onPushedCode(
        push({'type': 'otp', 'code': '4821', 'purpose': 'password_reset'}),
      );
      await Future<void>.delayed(Duration.zero);
      expect(f.auth.verifiedCode, '4821');
    });
  });

  test('ignores a push while a verify is already in flight', () {
    // Two verifies racing on the same code would spend two of the five attempts.
    controller
      ..state = const OtpFlowState(
        step: OtpStep.code,
        phone: '03001112233',
        code: '1111',
        busy: true,
      )
      ..onPushedCode(push({'type': 'otp', 'code': '4821'}));
    expect(container.read(otpFlowControllerProvider).code, '1111');
  });
}

/// Records what was verified, so the test can assert the PUSHED code is the one that went
/// to the server rather than whatever happened to be in the boxes.
class _FakeAuth implements AuthRepository {
  String? verifiedCode;

  @override
  Future<String> verifyOtp({
    required String phone,
    required String code,
    OtpPurpose purpose = OtpPurpose.passwordSetup,
  }) async {
    verifiedCode = code;
    return 'set-password-token';
  }

  // Nothing else on the flow touches the repository in this test; anything that did would
  // fail loudly here rather than silently returning a default.
  @override
  dynamic noSuchMethod(Invocation invocation) =>
      throw UnimplementedError('${invocation.memberName} not stubbed');
}
