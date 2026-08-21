import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/core/env/app_env.dart';
import 'package:mtag_user_app/core/network/tls_pinning.dart';

/// Pinning configuration.
///
/// The test binary has no `--dart-define`s, so it runs as the `dev` flavour. That is
/// enough to pin down the two behaviours that matter and are easy to get backwards.
void main() {
  group('configureTlsPinning', () {
    test('does nothing on a non-prod flavour', () {
      // dev and lan talk to a plain-HTTP Django server, so a pin there would either be
      // vacuous or would break the profile operators actually test on.
      expect(AppEnv.isProd, isFalse);

      final dio = Dio();
      final before = dio.interceptors.length;
      configureTlsPinning(dio);
      expect(dio.interceptors.length, before);
    });
  });

  group('computePin', () {
    test('produces the sha256/base64 form the interceptor compares against', () {
      // The empty-input SHA-256 is a known constant, which makes this a real check that
      // the encoding matches the README's openssl recipe rather than a tautology.
      expect(
        computePin(const []),
        'sha256/47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=',
      );
    });

    test('is stable for the same bytes and differs for different ones', () {
      expect(computePin(const [1, 2, 3]), computePin(const [1, 2, 3]));
      expect(computePin(const [1, 2, 3]), isNot(computePin(const [1, 2, 4])));
    });
  });

  group('AppEnv.certificatePins', () {
    test(
      'is empty without the define, which is what makes a prod build fail loudly',
      () {
        // configureTlsPinning THROWS on prod with no pins rather than asserting, because an
        // assert is stripped from release — the only build that branch can be reached in —
        // and would ship an unpinned APK that every code path claims is pinned.
        expect(AppEnv.certificatePins, isEmpty);
      },
    );

    test('an ABSENT define is not the same as an opted-out one', () {
      // The distinction this whole mechanism rests on. Both end with pinning off, but only
      // one of them is a decision: an absent define must still crash a prod build in QA,
      // while the sentinel is how a Let's Encrypt host says "unpinned, on purpose".
      //
      // A regression that made the sentinel the DEFAULT would turn every forgotten flag
      // into a silently unpinned release — the exact failure the throw exists to prevent.
      expect(AppEnv.pinningExplicitlyDisabled, isFalse);
    });
  });

  group('AppEnv flavour resolution', () {
    test('dev falls back to the emulator host', () {
      expect(AppEnv.resolvedApiBase, 'http://10.0.2.2:8000');
    });

    test('apiRoot appends /api/v1/ exactly once', () {
      expect(AppEnv.apiRoot, 'http://10.0.2.2:8000/api/v1/');
    });

    test('business rules mirror the server constants', () {
      // settings.MINIMUM_ACCOUNT_BALANCE and InitiateTopupSerializer's min_value. These
      // are duplicated so the app can WARN, never so it can decide.
      expect(AppEnv.minimumEntryBalance, 50);
      expect(AppEnv.minimumTopupAmount, 100);
      // The soft threshold must sit above the hard one or the two banners contradict.
      expect(AppEnv.lowBalanceWarning > AppEnv.minimumEntryBalance, isTrue);
    });

    test('self-registration and the unimplemented gateways are OFF by default', () {
      // /auth/register/ has no phone verification, and the backend now refuses anonymous
      // registration outright. Easypaisa and card have no backend of any kind.
      expect(AppEnv.registrationEnabled, isFalse);
      expect(AppEnv.easypaisaEnabled, isFalse);
      expect(AppEnv.cardEnabled, isFalse);
      // And app-initiated checkout is unconfigured, which is its normal state.
      expect(AppEnv.appInitiatedCheckoutConfigured, isFalse);
    });
  });
}
