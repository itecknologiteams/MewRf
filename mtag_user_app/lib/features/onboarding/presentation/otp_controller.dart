import 'dart:async';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/data/auth_repository.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/features/auth/presentation/session_controller.dart';
import 'package:mtag_user_app/features/notifications/data/push_service.dart';

/// Where the setup flow has got to.
enum OtpStep { phone, code, password, done }

class OtpFlowState {
  const OtpFlowState({
    this.step = OtpStep.phone,
    this.phone = '',
    this.code = '',
    this.token,
    this.delivery,
    this.pushedToDevices = false,
    this.purpose = OtpPurpose.passwordSetup,
    this.busy = false,
    this.error,
    this.attemptsLeft,
    this.resendIn = 0,
  });

  final OtpStep step;
  final String phone;

  /// Digits entered so far. Never longer than [codeLength].
  final String code;

  /// The short-lived authorisation from a successful verify.
  final String? token;

  /// 'console' when the server has no SMS gateway — the UI says so rather than promising
  /// an SMS that will not arrive.
  final String? delivery;

  /// The server also pushed the code to a device already signed in to this account, so the
  /// screen can point at the notification rather than at an SMS that may be slower.
  ///
  /// The app never REQUESTS push delivery — the server derives the destination from the
  /// account's registered devices, precisely so that asking for a code cannot direct it at
  /// the asker's own handset.
  final bool pushedToDevices;

  /// Which flow this is. Carried in state rather than passed at each call so the OTP and
  /// password screens — which are shared between first-time setup and forgot-password —
  /// cannot drift out of step with the token they are about to spend.
  final OtpPurpose purpose;

  final bool busy;
  final String? error;

  /// Remaining guesses, when the server tells us.
  final int? attemptsLeft;

  /// Seconds until Resend is allowed again.
  final int resendIn;

  static const codeLength = 4;

  bool get isCodeComplete => code.length == codeLength;

  OtpFlowState copyWith({
    OtpStep? step,
    String? phone,
    String? code,
    String? token,
    String? delivery,
    bool? pushedToDevices,
    OtpPurpose? purpose,
    bool? busy,
    String? error,
    int? attemptsLeft,
    int? resendIn,
    bool clearError = false,
  }) => OtpFlowState(
    step: step ?? this.step,
    phone: phone ?? this.phone,
    code: code ?? this.code,
    token: token ?? this.token,
    delivery: delivery ?? this.delivery,
    pushedToDevices: pushedToDevices ?? this.pushedToDevices,
    purpose: purpose ?? this.purpose,
    busy: busy ?? this.busy,
    error: clearError ? null : (error ?? this.error),
    attemptsLeft: attemptsLeft ?? this.attemptsLeft,
    resendIn: resendIn ?? this.resendIn,
  );
}

/// Drives first-time password setup: phone → code → password → signed in.
class OtpFlowController extends Notifier<OtpFlowState> {
  Timer? _resendTimer;

  @override
  OtpFlowState build() {
    ref.onDispose(() {
      _resendTimer?.cancel();
      // Leaking this would keep an FCM subscription alive for the life of the process,
      // writing into a controller nobody is watching.
      _stopListeningForPushedCode();
    });
    return const OtpFlowState();
  }

  //: Long enough that Resend is not a free way to spam someone else's phone, and it matches
  //: the server's 5/minute throttle rather than letting the UI invite a 429.
  static const _resendCooldown = 30;

  void setPhone(String phone) =>
      state = state.copyWith(phone: phone, clearError: true);

  /// Begins a flow, fixing which one it is for its whole duration.
  ///
  /// Resets the accumulated state as well as the phone: re-entering from "Forgot password"
  /// after abandoning a setup halfway would otherwise inherit the old code, the old error
  /// and — worst — the old purpose, and spend a setup token against the reset endpoint.
  void start({required String phone, required OtpPurpose purpose}) {
    state = OtpFlowState(phone: phone, purpose: purpose);
  }

  bool get isReset => state.purpose == OtpPurpose.passwordReset;

  /// Appends a digit, and auto-verifies on the last one.
  ///
  /// The reference screen says "It'll auto-verify once entered", so there is no submit
  /// button — waiting for a tap after the fourth digit would be a button whose only job is
  /// to confirm what the user just finished doing.
  void pushDigit(String digit) {
    if (state.busy || state.isCodeComplete) return;
    final next = state.code + digit;
    state = state.copyWith(code: next, clearError: true);
    if (next.length == OtpFlowState.codeLength) unawaited(verify());
  }

  void popDigit() {
    if (state.busy || state.code.isEmpty) return;
    state = state.copyWith(
      code: state.code.substring(0, state.code.length - 1),
      clearError: true,
    );
  }

  /// Fills the code in when it arrives as a push, and verifies.
  ///
  /// ## Why this listener has to exist here
  ///
  /// On Android a NOTIFICATION message that arrives while the app is in the foreground is
  /// not rendered in the system tray — it is handed to `FirebaseMessaging.onMessage`
  /// instead. The app's only foreground listener lives in `AppShell`, which is mounted
  /// inside the AUTHENTICATED shell, and onboarding happens before there is a session. So
  /// the push landed, FCM reported success, the server logged a delivery, and nothing on the
  /// device consumed it: the code simply vanished while the user watched an empty OTP
  /// screen.
  ///
  /// Subscribing from the flow controller covers exactly the window the OTP screen is open.
  StreamSubscription<RemoteMessage>? _pushSub;

  void _listenForPushedCode() {
    if (_pushSub != null) return;
    try {
      _pushSub = _pushedCodes().listen(onPushedCode);
    } on Object {
      // No Firebase on this build, or no platform channel at all (every widget test runs
      // on the Dart VM). Auto-fill is a convenience; the user can still read the code and
      // type it, so this must never break the flow that delivers it.
    }
  }

  /// Separated so the failure above can be caught: touching the static stream is itself
  /// what throws when there is no platform channel behind it.
  Stream<RemoteMessage> _pushedCodes() => FirebaseMessaging.onMessage;

  /// When the current code was asked for. Anything older than this is a different code.
  DateTime? _requestedAt;

  /// How far before [_requestedAt] a push may claim to have been sent and still be trusted.
  ///
  /// `sentTime` comes from FCM's clock and is compared against the device's, so a little
  /// slack is needed. Ten seconds is far tighter than the gap between two real code
  /// requests — the resend cooldown alone is thirty — and far looser than any plausible
  /// clock skew.
  static const _pushClockSlack = Duration(seconds: 10);

  /// The request timestamp, exposed for tests. The real value is stamped by [requestCode],
  /// which cannot run without a server, so the staleness guard would otherwise be
  /// unreachable from a unit test.
  @visibleForTesting
  DateTime? get requestedAtForTest => _requestedAt;

  @visibleForTesting
  set requestedAtForTest(DateTime? at) => _requestedAt = at;

  @visibleForTesting
  void onPushedCode(RemoteMessage message) {
    if (message.data['type'] != 'otp') return;

    final code = (message.data['code'] ?? '').toString();
    // Only the dev delivery path carries the code. On a production server the push has no
    // `code` field, so this is inert and the user types what they read — which is the
    // intended behaviour there, not a gap.
    if (code.length != OtpFlowState.codeLength) return;
    // Not while a verify is already in flight, and not once the flow has moved on: a
    // late-arriving push must not overwrite the password step with a spent code.
    if (state.busy || state.step != OtpStep.code) return;

    // A push for a DIFFERENT flow must not be spent here — the server derives the token's
    // signing salt from the purpose, so a reset code auto-filled into a setup would be
    // refused and would look to the user like a wrong code.
    final pushedPurpose = message.data['purpose']?.toString();
    if (pushedPurpose != null && pushedPurpose != state.purpose.wire) return;

    // STALE-CODE GUARD, and it earned its place: a code redelivered by FCM when the app
    // reconnected was auto-filled and verified 176ms after a fresh request had been made,
    // spending one of the five attempts the account gets — and then the failed verify ate
    // into the shared OTP throttle, so the user was rate-limited for a code they had never
    // typed. FCM queues undelivered messages and hands them over on reconnect, so an
    // hours-old code arriving now is normal, not exotic.
    final requestedAt = _requestedAt;
    final sentTime = message.sentTime;
    if (requestedAt != null &&
        sentTime != null &&
        sentTime.isBefore(requestedAt.subtract(_pushClockSlack))) {
      return;
    }

    state = state.copyWith(code: code, clearError: true);
    unawaited(verify());
  }

  void _stopListeningForPushedCode() {
    unawaited(_pushSub?.cancel());
    _pushSub = null;
  }

  /// This handset's FCM token, or null if there is none to be had.
  ///
  /// Sent with the OTP request so a development server running
  /// `OTP_PUSH_TO_REQUESTING_DEVICE` can deliver the code to the phone in the tester's
  /// hand. Production servers ignore it — a code is only ever pushed to devices the account
  /// has already registered — so this is inert there rather than conditional here, which
  /// keeps one build working against every environment.
  ///
  /// Everything about it is best-effort. This runs BEFORE the user has an account, and no
  /// part of onboarding may depend on Firebase being configured, on the notification
  /// permission being granted, or on Play services existing at all: the SMS is the channel
  /// that matters, and a failure to get a token must not stop the code being sent.
  Future<String?> _deviceToken() async {
    try {
      final service = PushService();
      if (await service.initialise() != PushAvailability.ready) return null;
      // Asked here rather than at first launch because the reason is now obvious to the
      // user: they are waiting for a code, and the code arrives as a notification.
      if (await service.requestPermission() != PushAvailability.ready) return null;
      return (await service.registration())?.token;
    } on Object {
      return null;
    }
  }

  Future<bool> requestCode() async {
    state = state.copyWith(busy: true, clearError: true);
    try {
      final delivery = await ref
          .read(authRepositoryProvider)
          .requestOtp(
            phone: state.phone,
            deviceToken: await _deviceToken(),
            // MUST be the same purpose `verify` and `setPassword` will send. The server
            // scopes the OTP row by (phone, purpose) and derives the token's signing salt
            // from it, so a request/verify mismatch does not fail loudly — it reports
            // `not_found`, which is indistinguishable on screen from a mistyped code.
            purpose: state.purpose,
          );
      state = state.copyWith(
        busy: false,
        step: OtpStep.code,
        code: '',
        delivery: delivery.primary,
        pushedToDevices: delivery.reachedThisAccountsDevices,
      );
      // Stamped BEFORE the listener is attached, so a push that arrives in the same
      // instant is measured against this request rather than the previous one.
      _requestedAt = DateTime.now();
      // Attached only once a code is actually in flight, so the app is not holding an FCM
      // subscription open across the whole of onboarding.
      _listenForPushedCode();
      _startResendCooldown();
      return true;
    } on Object catch (error) {
      state = state.copyWith(busy: false, error: error.toString());
      return false;
    }
  }

  Future<bool> verify() async {
    state = state.copyWith(busy: true, clearError: true);
    try {
      final token = await ref
          .read(authRepositoryProvider)
          .verifyOtp(
            phone: state.phone,
            code: state.code,
            purpose: state.purpose,
          );
      state = state.copyWith(busy: false, token: token, step: OtpStep.password);
      // Verified — the code is spent, so a late-arriving push must not overwrite the
      // password screen's state with a dead code.
      _stopListeningForPushedCode();
      return true;
    } on Object catch (error) {
      // The code stays on screen so the user can correct a digit rather than retype all
      // four — but it is cleared when the code is burned, since retrying is pointless then.
      state = state.copyWith(busy: false, error: error.toString(), code: '');
      return false;
    }
  }

  Future<bool> setPassword(String password) async {
    final token = state.token;
    if (token == null) return false;
    state = state.copyWith(busy: true, clearError: true);
    try {
      await ref
          .read(authRepositoryProvider)
          .setPasswordWithOtp(
            token: token,
            password: password,
            phone: state.phone,
            purpose: state.purpose,
          );
      // The server already returned session cookies; this makes the router notice.
      // The server already set session cookies; re-running the probe is what makes the
      // router see a signed-in session and move to the dashboard.
      await ref.read(sessionControllerProvider.notifier).retry();
      state = state.copyWith(busy: false, step: OtpStep.done);
      return true;
    } on Object catch (error) {
      state = state.copyWith(busy: false, error: error.toString());
      return false;
    }
  }

  void _startResendCooldown() {
    _resendTimer?.cancel();
    state = state.copyWith(resendIn: _resendCooldown);
    _resendTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      final left = state.resendIn - 1;
      state = state.copyWith(resendIn: left < 0 ? 0 : left);
      if (left <= 0) timer.cancel();
    });
  }

  void reset() {
    _resendTimer?.cancel();
    state = const OtpFlowState();
  }
}

final otpFlowControllerProvider =
    NotifierProvider<OtpFlowController, OtpFlowState>(OtpFlowController.new);
