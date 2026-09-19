import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/core/data/auth_repository.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/user.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/features/onboarding/presentation/otp_controller.dart';

/// The forgot-password flow, which shares every screen with first-time setup.
///
/// Because they share screens, the only thing keeping them apart is `purpose` — and the
/// server derives the token's signing salt from it. A flow that carried the wrong purpose
/// would not fail visibly; it would spend a setup token against the reset endpoint, be
/// refused, and look to the user like "that code is not correct".
///
/// A reset also revokes every other session, which a setup does not. Getting the purpose
/// wrong in the other direction would therefore silently skip that revocation — the one
/// thing that makes a reset worth having when the reason for it is that somebody else is in
/// your account.
void main() {
  late ProviderContainer container;
  late OtpFlowController controller;

  setUp(() {
    container = ProviderContainer();
    addTearDown(container.dispose);
    controller = container.read(otpFlowControllerProvider.notifier);
  });

  test('a new flow defaults to setup', () {
    expect(
      container.read(otpFlowControllerProvider).purpose,
      OtpPurpose.passwordSetup,
    );
  });

  test('start() fixes the purpose for the whole flow', () {
    controller.start(
      phone: '03001112233',
      purpose: OtpPurpose.passwordReset,
    );
    final state = container.read(otpFlowControllerProvider);
    expect(state.purpose, OtpPurpose.passwordReset);
    expect(state.phone, '03001112233');
    expect(controller.isReset, isTrue);
  });

  test('start() clears state left over from an abandoned flow', () {
    // The scenario: a user begins setup, types two digits, backs out, and taps "Forgot
    // password". Without a reset here they would inherit the half-typed code, the stale
    // error, and — the one that actually breaks — the previous PURPOSE, sending a setup
    // token to the reset endpoint.
    controller
      ..start(phone: '03001112233', purpose: OtpPurpose.passwordSetup)
      ..state = controller.state.copyWith(
        code: '12',
        error: 'that code is not correct',
        token: 'stale-setup-token',
        step: OtpStep.code,
      );

    // Proves the stale state is genuinely there before asserting it is cleared — otherwise
    // this test would still pass if `copyWith` above silently did nothing.
    expect(container.read(otpFlowControllerProvider).code, '12');

    controller.start(phone: '03009998877', purpose: OtpPurpose.passwordReset);

    final state = container.read(otpFlowControllerProvider);
    expect(state.purpose, OtpPurpose.passwordReset);
    expect(state.phone, '03009998877');
    expect(state.code, isEmpty);
    expect(state.error, isNull);
    expect(state.token, isNull);
    expect(state.step, OtpStep.phone);
  });

  group('every call in one flow uses the SAME purpose', () {
    /// The bug this group exists for.
    ///
    /// `requestCode` was passing no purpose at all, so it defaulted to `password_setup`
    /// while `verify` sent `password_reset`. The server scopes the OTP row by
    /// (phone, purpose), so it found nothing and answered `not_found` — which the app
    /// renders as "Something went wrong. Try again." That is indistinguishable on screen
    /// from a mistyped code, and it cost several rounds of chasing FCM and push
    /// configuration before the server was asked to log what it had actually received.
    ///
    /// Nothing failed loudly at any layer. The only way to catch it is to assert that one
    /// flow speaks with one voice.
    Future<void> runFlow(OtpPurpose purpose, _PurposeSpy spy) async {
      final scoped = ProviderContainer(
        overrides: [authRepositoryProvider.overrideWithValue(spy)],
      );
      addTearDown(scoped.dispose);

      final c = scoped.read(otpFlowControllerProvider.notifier)
        ..start(phone: '03001112233', purpose: purpose);
      await c.requestCode();
      c.state = c.state.copyWith(code: '4821');
      await c.verify();
      await c.setPassword('brandnewpass456');
    }

    for (final purpose in OtpPurpose.values) {
      test('${purpose.wire} reaches request, verify and setPassword', () async {
        final spy = _PurposeSpy();
        await runFlow(purpose, spy);

        expect(
          spy.purposes,
          {
            'request': purpose,
            'verify': purpose,
            'setPassword': purpose,
          },
          reason:
              'a flow that changes purpose midway gets `not_found` from the server, '
              'which the UI shows as a generic failure',
        );
      });
    }
  });

  test('the wire values are exactly what the server accepts', () {
    // The server refuses an unrecognised purpose rather than defaulting to setup, so these
    // strings are load-bearing: a typo here is a 400 on every reset, not a silent fallback.
    expect(OtpPurpose.passwordSetup.wire, 'password_setup');
    expect(OtpPurpose.passwordReset.wire, 'password_reset');
  });

  test('copyWith preserves the purpose when other fields change', () {
    // Every step of the flow goes through copyWith. A purpose dropped anywhere along the
    // way would surface only at set-password, as an invalid token.
    controller.start(phone: '03001112233', purpose: OtpPurpose.passwordReset);
    final moved = controller.state.copyWith(step: OtpStep.code, code: '4821');
    expect(moved.purpose, OtpPurpose.passwordReset);
  });
}

/// Records the purpose every call receives.
class _PurposeSpy implements AuthRepository {
  final purposes = <String, OtpPurpose>{};

  @override
  Future<OtpDelivery> requestOtp({
    required String phone,
    String? deviceToken,
    OtpPurpose purpose = OtpPurpose.passwordSetup,
  }) async {
    purposes['request'] = purpose;
    return const OtpDelivery(primary: 'console', channels: ['console']);
  }

  @override
  Future<String> verifyOtp({
    required String phone,
    required String code,
    OtpPurpose purpose = OtpPurpose.passwordSetup,
  }) async {
    purposes['verify'] = purpose;
    return 'set-password-token';
  }

  @override
  Future<LoginResult> setPasswordWithOtp({
    required String token,
    required String password,
    required String phone,
    bool rememberPhone = true,
    OtpPurpose purpose = OtpPurpose.passwordSetup,
  }) async {
    purposes['setPassword'] = purpose;
    return const LoginResult(
      userId: 1,
      uuid: 'u',
      fullName: 'Holder',
      phone: '03001112233',
      role: UserRole.user,
    );
  }

  @override
  dynamic noSuchMethod(Invocation invocation) =>
      throw UnimplementedError('${invocation.memberName} not stubbed');
}
