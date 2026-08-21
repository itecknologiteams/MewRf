import 'package:mtag_user_app/core/cache/cache_database.dart';
import 'package:mtag_user_app/core/errors/app_failure.dart';
import 'package:mtag_user_app/core/models/user.dart';
import 'package:mtag_user_app/core/network/api_client.dart';
import 'package:mtag_user_app/core/storage/secure_store.dart';

/// Auth. Cookie-based throughout — there is no token for this class to hold.
class AuthRepository {
  AuthRepository({
    required ApiClient client,
    required CacheDatabase cache,
    required SecureStore secureStore,
  }) : _client = client,
       _cache = cache,
       _secureStore = secureStore;

  final ApiClient _client;
  final CacheDatabase _cache;
  final SecureStore _secureStore;

  /// Logs in. On success the session cookies are already in the jar — the cookie
  /// manager put them there from `Set-Cookie` — so there is nothing to store.
  ///
  /// A failed login returns HTTP **401** with the reason under
  /// `errors.non_field_errors`, not under `phone` or `password`:
  ///   * wrong credentials -> "Invalid phone number or password."
  ///   * blocked account    -> "Account is blocked. Contact support."
  /// The login controller reads [AppFailure.nonFieldError] and distinguishes the
  /// blocked case, which is a dead end needing a support number rather than a
  /// retry.
  Future<LoginResult> login({
    required String phone,
    required String password,
    bool rememberPhone = true,
  }) async {
    final data = await _client.post<LoginResult>(
      'auth/login/',
      body: {'phone': phone, 'password': password},
      parse: (data) => LoginResult.fromApi(data as Map<String, dynamic>),
    );

    if (data == null) {
      throw const MalformedResponseFailure(
        message: 'Login succeeded but returned no user',
      );
    }

    if (rememberPhone) {
      await _secureStore.writeRememberedPhone(phone);
    } else {
      await _secureStore.clearRememberedPhone();
    }

    return data;
  }

  // ── First-time password setup, verified by SMS code ───────────────────────
  //
  // Fills the gap that made this app unusable for a real customer: booths create the
  // account when the tag is fitted, but nobody ever hands the holder a password.
  //
  // Note this is NOT signup. The server refuses an unknown number, so the app cannot
  // create accounts with no tag behind them.

  /// Whether this number has an account, and whether its holder has ever chosen a password.
  ///
  /// Asked BEFORE requesting a code so someone who already has a password is sent to the
  /// login screen rather than handed a verification code they do not need.
  ///
  /// `hasPassword` is the server's `password_set_at`, not Django's `has_usable_password()`:
  /// booth-created accounts carry a random password the customer was never told, so the
  /// built-in flag is true for precisely the people who still need setup.
  Future<PhoneStatus> phoneStatus({required String phone}) async {
    final status = await _client.post<PhoneStatus>(
      'auth/phone-status/',
      body: {'phone': phone},
      parse: (data) => PhoneStatus.fromApi(data as Map<String, dynamic>),
    );
    return status ?? const PhoneStatus();
  }

  /// Asks the server to send a 4-digit code. Returns how it was delivered.
  ///
  /// `delivery` is 'console' on any build with no SMS gateway configured — the code goes to
  /// the server log instead. Surfaced so the UI can say so rather than telling the user to
  /// watch for an SMS that is never coming.
  ///
  /// `channels` lists EVERY channel that carried the code. The server also pushes it to
  /// devices already signed in to this account, so a returning holder can be told to check
  /// their notifications instead of waiting on an SMS.
  ///
  /// [deviceToken] is this handset's FCM token, and the server IGNORES it unless it is
  /// running with `OTP_PUSH_TO_REQUESTING_DEVICE` — a development setting that
  /// `config.settings.production` refuses to boot with. It exists because there is no SMS
  /// gateway yet: the console sender writes the code to the server log, which cannot be
  /// read from a phone, so the onboarding flow could not be exercised on a real device at
  /// all.
  ///
  /// Sending it unconditionally keeps one client build working against every environment;
  /// what differs is whether the server is willing to act on it. It is NOT a request for
  /// push delivery — the client cannot ask for that, and on a production server a code is
  /// only ever pushed to devices the account has already registered.
  Future<OtpDelivery> requestOtp({
    required String phone,
    String? deviceToken,
    OtpPurpose purpose = OtpPurpose.passwordSetup,
  }) async {
    final delivery = await _client.post<OtpDelivery>(
      'auth/otp/request/',
      body: {
        'phone': phone,
        'purpose': purpose.wire,
        if (deviceToken != null && deviceToken.isNotEmpty)
          'device_token': deviceToken,
      },
      parse: (data) {
        final map = data is Map<String, dynamic>
            ? data
            : const <String, dynamic>{};
        final raw = map['channels'];
        return OtpDelivery(
          primary: map['delivery']?.toString() ?? 'unknown',
          // Absent on an older server, which is why it falls back to the single value
          // rather than to an empty list — an empty list would read as "delivered nowhere".
          channels: raw is List
              ? raw.map((e) => e.toString()).toList(growable: false)
              : [map['delivery']?.toString() ?? 'unknown'],
        );
      },
    );
    return delivery ??
        const OtpDelivery(primary: 'unknown', channels: ['unknown']);
  }

  /// Exchanges a code for a short-lived token authorising the password change.
  Future<String> verifyOtp({
    required String phone,
    required String code,
    OtpPurpose purpose = OtpPurpose.passwordSetup,
  }) async {
    final token = await _client.post<String>(
      'auth/otp/verify/',
      body: {'phone': phone, 'code': code, 'purpose': purpose.wire},
      parse: (data) =>
          (data as Map<String, dynamic>)['token']?.toString() ?? '',
    );
    if (token == null || token.isEmpty) {
      throw const MalformedResponseFailure(
        message: 'Verification succeeded but returned no token',
      );
    }
    return token;
  }

  /// Sets the password and signs in — the server returns session cookies, so there is no
  /// second login step. Making someone retype the password they chose one screen earlier is
  /// friction with no security value.
  /// [purpose] MUST match the flow the token came from. The server derives the token's
  /// signing salt from it, so a mismatch fails the signature check rather than quietly
  /// taking the wrong path — which for a reset would mean skipping session revocation.
  Future<LoginResult> setPasswordWithOtp({
    required String token,
    required String password,
    required String phone,
    bool rememberPhone = true,
    OtpPurpose purpose = OtpPurpose.passwordSetup,
  }) async {
    final data = await _client.post<LoginResult>(
      'auth/otp/set-password/',
      body: {
        'token': token,
        'new_password': password,
        'confirm_password': password,
        'purpose': purpose.wire,
      },
      parse: (data) => LoginResult.fromApi(data as Map<String, dynamic>),
    );
    if (data == null) {
      throw const MalformedResponseFailure(
        message: 'Password was set but no session was returned',
      );
    }
    if (rememberPhone) {
      await _secureStore.writeRememberedPhone(phone);
    }
    return data;
  }

  /// The session-validity probe, used on cold start.
  ///
  /// This is the only reliable check. A cookie in the jar proves nothing:
  /// `CookieJWTAuthentication` deliberately treats an unusable access-token cookie
  /// as anonymous rather than as an error, so a stale jar produces a 401 from the
  /// permission layer — which the refresh interceptor will try to fix before this
  /// call's failure ever surfaces.
  Future<AppUser> me() => _client.get<AppUser>(
    'auth/me/',
    parse: (data) => AppUser.fromApi(data as Map<String, dynamic>),
  );

  /// Updates the profile. Only `full_name` and `cnic` — the server now refuses the
  /// rest, and it is not the app's place to ask.
  Future<AppUser> updateProfile({String? fullName, String? cnic}) async {
    final data = await _client.patch<AppUser>(
      'auth/me/',
      body: {
        'full_name': ?fullName,
        'cnic': ?cnic,
      },
      parse: (data) => AppUser.fromApi(data as Map<String, dynamic>),
    );
    if (data == null) {
      throw const MalformedResponseFailure(
        message: 'Profile update returned no user',
      );
    }
    return data;
  }

  /// Changes the password. Minimum 8 characters, enforced server-side too.
  Future<void> changePassword({
    required String oldPassword,
    required String newPassword,
  }) => _client.post<void>(
    'auth/change-password/',
    body: {'old_password': oldPassword, 'new_password': newPassword},
  );

  /// Logs out.
  ///
  /// The server call blacklists the refresh token, which matters — without it a
  /// leaked cookie stays valid for its remaining 7 days. But the local session is
  /// cleared **regardless of the outcome**: a user who taps Log Out on a dead
  /// connection must end up logged out, not stuck in a session they asked to leave.
  Future<void> logout() async {
    try {
      await _client.post<void>('auth/logout/');
    } on AppFailure {
      // Deliberately swallowed. See above.
    } finally {
      await _client.clearSession();
      // The cache goes too: a cached balance surviving a logout would show the
      // previous user's money to whoever signs in next, and a shared handset is
      // normal here.
      await _cache.clearAll();
    }
  }

  Future<String?> rememberedPhone() => _secureStore.readRememberedPhone();
}

/// What `/auth/phone-status/` reports about a number.
class PhoneStatus {
  const PhoneStatus({
    this.exists = false,
    this.hasPassword = false,
    this.blocked = false,
    this.isStaffAccount = false,
  });

  factory PhoneStatus.fromApi(Map<String, dynamic> json) => PhoneStatus(
    exists: json['exists'] == true,
    hasPassword: json['has_password'] == true,
    blocked: json['blocked'] == true,
    isStaffAccount: json['is_staff_account'] == true,
  );

  final bool exists;

  /// The holder has chosen a password, so they should be signing in, not setting one up.
  final bool hasPassword;

  final bool blocked;

  /// The consumer app refuses staff logins, so it can say so before they try.
  final bool isStaffAccount;
}

/// How an OTP actually reached the user.
class OtpDelivery {
  const OtpDelivery({required this.primary, required this.channels});

  /// The first channel that carried it. Kept because the UI's copy branches on 'console'.
  final String primary;

  /// Every channel that carried it: 'push', 'console', a gateway name.
  final List<String> channels;

  /// True when a device already signed in to this account received it as a notification.
  bool get reachedThisAccountsDevices => channels.contains('push');

  bool get isConsoleOnly =>
      channels.length == 1 && channels.first == 'console';
}

/// Why a verification code was issued.
///
/// The server keeps these strictly apart — a code or token minted for one cannot satisfy
/// the other — because the outcomes differ. Completing a RESET revokes every existing
/// session, on the reasoning that the usual reason to reset is believing somebody else is
/// in the account; a 7-day refresh token would otherwise keep working for that somebody
/// long after the holder thought they had locked them out.
enum OtpPurpose {
  /// An account created at a booth that has never had a password.
  passwordSetup('password_setup'),

  /// Forgot password, for a holder who already has one.
  passwordReset('password_reset');

  const OtpPurpose(this.wire);

  /// Exactly the value `apps/users/models.py OtpPurpose` accepts. The server refuses an
  /// unrecognised purpose rather than defaulting, so this string is load-bearing.
  final String wire;
}
