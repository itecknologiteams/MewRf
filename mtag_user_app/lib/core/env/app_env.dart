/// Build-time configuration. Everything here comes from `--dart-define`.
///
/// Nothing in this file has a production default that would silently work. A
/// missing base URL throws at startup rather than falling back to localhost,
/// because a release build quietly pointing at `10.0.2.2` is a build that looks
/// fine in CI and cannot reach anything on a real phone.
library;

enum AppFlavor {
  /// Android emulator against a local runserver.
  dev,

  /// Physical device on the toll LAN, plain HTTP.
  lan,

  /// HTTPS, certificate-pinned.
  prod,
}

abstract final class AppEnv {
  /// `{{BASE}}` — the scheme+host, WITHOUT the `/api/v1/` suffix.
  static const String apiBase = String.fromEnvironment('MTAG_API_BASE');

  static const String _flavorName = String.fromEnvironment(
    'MTAG_FLAVOR',
    defaultValue: 'dev',
  );

  static AppFlavor get flavor => switch (_flavorName) {
    'prod' => AppFlavor.prod,
    'lan' => AppFlavor.lan,
    _ => AppFlavor.dev,
  };

  static bool get isProd => flavor == AppFlavor.prod;

  /// The API root every request is relative to.
  static String get apiRoot {
    final base = resolvedApiBase;
    final trimmed = base.endsWith('/')
        ? base.substring(0, base.length - 1)
        : base;
    return '$trimmed/api/v1/';
  }

  /// The base URL, with per-flavour development defaults.
  ///
  /// dev and lan get the documented hosts as a convenience. prod deliberately
  /// does not: shipping a release with a placeholder host is the failure this
  /// guards against, and it is better to crash on the first frame in QA than to
  /// hand a user an app that cannot log in.
  static String get resolvedApiBase {
    if (apiBase.isNotEmpty) return apiBase;
    return switch (flavor) {
      AppFlavor.dev => 'http://10.0.2.2:8000',
      AppFlavor.lan => 'http://192.168.78.200:8000',
      AppFlavor.prod => throw StateError(
        'MTAG_API_BASE is required for the prod flavour. Build with '
        '--dart-define=MTAG_API_BASE=https://your-host',
      ),
    };
  }

  /// SHA-256 certificate pins for the prod host, comma-separated, base64.
  ///
  /// Format: `sha256/AAAA…=`, matching the digest `_PinValidationInterceptor`
  /// computes over the peer's DER. Supply at least two — the live leaf and its
  /// replacement — or a rotation bricks every installed app until users update.
  ///
  /// The literal value `none` disables pinning for the build. That opt-out exists
  /// because pinning is not viable against every issuer: this app pins the LEAF
  /// certificate, and a Let's Encrypt leaf is reissued about every 60 days with a
  /// new serial, so its digest changes at each renewal. The "ship the backup pin
  /// first" mitigation cannot be followed there, because the next leaf does not
  /// exist until certbot issues it. See [pinningExplicitlyDisabled].
  static const String _pins = String.fromEnvironment('MTAG_CERT_PINS');

  /// Prints this device's FCM token to the log, for diagnosing push.
  ///
  /// OFF by default and never enabled in a shipped build. A registration token is a
  /// capability: anyone holding it can send notifications to that handset, so writing it to
  /// logcat — readable by any process with the permission — is a leak, not a log line.
  ///
  /// It exists because there is no other way to answer "does FCM actually reach this
  /// phone". Without the token you can only observe that the server sent something and
  /// nothing appeared, which is true of a dozen different faults.
  ///
  ///     flutter build apk … --dart-define=MTAG_LOG_PUSH_TOKEN=true
  static const bool logPushToken = bool.fromEnvironment('MTAG_LOG_PUSH_TOKEN');

  /// Whether this build opted out of pinning on purpose.
  ///
  /// Distinguishing "opted out" from "forgot the flag" is the entire point. An
  /// empty value still throws at launch, so a release built without any decision
  /// is caught in QA; only this explicit sentinel is allowed through.
  static bool get pinningExplicitlyDisabled {
    const off = {'none', 'off', 'disabled'};
    return off.contains(_pins.trim().toLowerCase());
  }

  static List<String> get certificatePins => pinningExplicitlyDisabled
      ? const <String>[]
      : _pins
            .split(',')
            .map((p) => p.trim())
            .where((p) => p.isNotEmpty)
            .toList(growable: false);

  // ── JazzCash ───────────────────────────────────────────────────────────────

  /// The gateway checkout URL the `jazzcash_payload` would be POSTed to.
  ///
  /// EMPTY BY DEFAULT, and the app must behave honestly when it is: the backend's
  /// `/payments/topup/` returns `pp_*` fields but no checkout URL, the merchant
  /// password is (correctly) withheld from the response, and
  /// JAZZCASH_VERIFY_HASH is off with the hashing formula still unconfirmed. So
  /// app-initiated checkout is NOT a working flow. With this unset the app shows
  /// the pending top-up plus the aggregator instructions rather than pretending
  /// to open a checkout. See README § "What is stubbed".
  static const String jazzCashCheckoutUrl = String.fromEnvironment(
    'MTAG_JAZZCASH_CHECKOUT_URL',
  );

  static bool get appInitiatedCheckoutConfigured =>
      jazzCashCheckoutUrl.isNotEmpty;

  /// Must match the backend's `JAZZCASH_RETURN_URL`. The in-app WebView watches
  /// for this prefix to know the redirect leg finished — which is a signal to go
  /// and ASK the server, never proof of payment on its own.
  static const String jazzCashReturnUrl = String.fromEnvironment(
    'MTAG_JAZZCASH_RETURN_URL',
  );

  /// Android package / iOS scheme for the JazzCash app, for the deep link on the
  /// aggregator instructions screen.
  static const String jazzCashAppScheme = String.fromEnvironment(
    'MTAG_JAZZCASH_APP_SCHEME',
    defaultValue: 'jazzcash://',
  );

  // ── Support ────────────────────────────────────────────────────────────────

  /// The recovery path for a forgotten password and the contact for a blocked
  /// account. There is no OTP endpoint on the backend, so this number IS the
  /// account-recovery flow and it must never be empty in a real build.
  /// Where the privacy policy lives.
  ///
  /// Injected, never hardcoded — the URL differs per deployment and this app ships to a
  /// LAN profile with no internet at all. EMPTY is a valid, handled state: the UI still
  /// shows the link (a payment app must disclose where its policy is) but explains it is
  /// not published yet and offers the support number instead of opening a dead URL.
  static const String privacyPolicyUrl = String.fromEnvironment(
    'MTAG_PRIVACY_URL',
  );

  static bool get hasPrivacyPolicy => privacyPolicyUrl.isNotEmpty;

  static const String supportPhone = String.fromEnvironment(
    'MTAG_SUPPORT_PHONE',
    defaultValue: '+922134400000',
  );

  static const String supportPhoneDisplay = String.fromEnvironment(
    'MTAG_SUPPORT_PHONE_DISPLAY',
    defaultValue: '021 3440 0000',
  );

  // ── Feature flags ──────────────────────────────────────────────────────────

  /// Self-registration. OFF, and it must stay off until the backend has phone
  /// verification: `POST /auth/register/` creates a `user` row from an unverified
  /// phone number. Real accounts are created at a booth. The backend now refuses
  /// anonymous registration too, so turning this on alone achieves nothing.
  static const bool registrationEnabled = bool.fromEnvironment(
    'MTAG_ENABLE_REGISTRATION',
  );

  /// Easypaisa has NO backend implementation of any kind. The gateway seam and
  /// the UI exist; the option renders as "coming soon" with retailer
  /// instructions. Never wire this to an invented endpoint.
  static const bool easypaisaEnabled = bool.fromEnvironment(
    'MTAG_ENABLE_EASYPAISA',
  );

  /// Card payments: same situation as Easypaisa.
  static const bool cardEnabled = bool.fromEnvironment('MTAG_ENABLE_CARD');

  // ── Business rules mirrored from the server ────────────────────────────────
  //
  // Duplicated client-side so the app can warn before a request is made, NOT so
  // it can decide. The server is the authority in every case; these values exist
  // to avoid bouncing the user off a validation they could have been told about.

  /// `settings.MINIMUM_ACCOUNT_BALANCE` — below this the barrier will not open.
  static const int minimumEntryBalance = 50;

  /// `InitiateTopupSerializer.amount.min_value` / `JazzCashService.initiate_topup`.
  static const int minimumTopupAmount = 100;

  /// Soft "top up soon" threshold. A client-side nicety, not a server rule.
  static const int lowBalanceWarning = 200;

  /// Tag expiry warning window.
  static const int tagExpiryWarningDays = 30;
}
