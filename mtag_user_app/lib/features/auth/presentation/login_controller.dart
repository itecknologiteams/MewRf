import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/errors/app_failure.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/features/auth/presentation/session_controller.dart';

/// The login form's state.
class LoginState {
  const LoginState({
    this.isSubmitting = false,
    this.fieldErrors = const {},
    this.failure,
    this.isBlockedAccount = false,
    this.cooldownSeconds = 0,
    this.rememberedPhone,
  });

  final bool isSubmitting;

  /// Straight from the envelope's `errors`, mapped onto the form.
  ///
  /// Note DRF's shape: bad credentials arrive under **`non_field_errors`**, not under
  /// `phone` or `password`, because `LoginSerializer.validate` raises on the whole
  /// payload. A form that only looked at per-field keys would show no error at all
  /// and leave the user tapping a button that appears to do nothing.
  final Map<String, String> fieldErrors;

  final AppFailure? failure;

  /// "Account is blocked. Contact support." — its own dead end, not a retryable
  /// error. Retrying cannot fix it and encouraging a retry wastes the 10/minute
  /// throttle on a user who needs a phone call.
  final bool isBlockedAccount;

  /// Live countdown after a 429. The login endpoint is throttled at 10/minute, which
  /// a user mistyping their password reaches in normal use.
  final int cooldownSeconds;

  final String? rememberedPhone;

  bool get isThrottled => cooldownSeconds > 0;

  bool get canSubmit => !isSubmitting && !isThrottled;

  String? get phoneError => fieldErrors['phone'];

  String? get passwordError => fieldErrors['password'];

  /// The credential error, which the server reports against the whole form.
  String? get formError =>
      fieldErrors['non_field_errors'] ?? fieldErrors['detail'];

  LoginState copyWith({
    bool? isSubmitting,
    Map<String, String>? fieldErrors,
    AppFailure? failure,
    bool clearFailure = false,
    bool? isBlockedAccount,
    int? cooldownSeconds,
    String? rememberedPhone,
  }) => LoginState(
    isSubmitting: isSubmitting ?? this.isSubmitting,
    fieldErrors: fieldErrors ?? this.fieldErrors,
    failure: clearFailure ? null : (failure ?? this.failure),
    isBlockedAccount: isBlockedAccount ?? this.isBlockedAccount,
    cooldownSeconds: cooldownSeconds ?? this.cooldownSeconds,
    rememberedPhone: rememberedPhone ?? this.rememberedPhone,
  );
}

class LoginController extends Notifier<LoginState> {
  Timer? _cooldownTimer;

  /// The exact wording `LoginSerializer` raises for a blocked account.
  ///
  /// Matched on the string because the server gives no machine-readable code for it —
  /// both this and "Invalid phone number or password." come back as HTTP 401 with a
  /// `non_field_errors` list, and the app needs to tell a dead end from a typo. Pinned
  /// by a backend test so a reworded message fails there rather than silently
  /// degrading this screen to a generic error.
  static const blockedMessage = 'Account is blocked. Contact support.';

  @override
  LoginState build() {
    ref.onDispose(() => _cooldownTimer?.cancel());
    Future.microtask(_loadRememberedPhone);
    return const LoginState();
  }

  Future<void> _loadRememberedPhone() async {
    final phone = await ref.read(authRepositoryProvider).rememberedPhone();
    if (phone != null && phone.isNotEmpty) {
      state = state.copyWith(rememberedPhone: phone);
    }
  }

  /// Clears errors as the user edits, so a stale "wrong password" does not sit under
  /// a field they have already corrected.
  void clearErrors() {
    if (state.fieldErrors.isEmpty && state.failure == null) return;
    state = state.copyWith(
      fieldErrors: const {},
      clearFailure: true,
      isBlockedAccount: false,
    );
  }

  Future<void> submit({
    required String phone,
    required String password,
    required bool rememberPhone,
  }) async {
    if (!state.canSubmit) return;

    state = state.copyWith(
      isSubmitting: true,
      fieldErrors: const {},
      clearFailure: true,
      isBlockedAccount: false,
    );

    try {
      await ref
          .read(sessionControllerProvider.notifier)
          .signIn(
            phone: phone,
            password: password,
            rememberPhone: rememberPhone,
          );
      // The router redirects on the session state; nothing to do here. State is not
      // reset because this controller is about to be disposed with the screen.
    } on ThrottledFailure catch (failure) {
      state = state.copyWith(isSubmitting: false, failure: failure);
      _startCooldown(failure.retryAfter ?? const Duration(seconds: 60));
    } on AppFailure catch (failure) {
      final nonField = failure.nonFieldError ?? '';
      state = state.copyWith(
        isSubmitting: false,
        failure: failure,
        fieldErrors: failure.fieldErrors ?? const {},
        isBlockedAccount: nonField.contains(blockedMessage),
      );
    }
  }

  /// Ticks the 429 cooldown down to zero.
  ///
  /// A real countdown rather than a disabled button with no explanation: a user who
  /// cannot see how long they are locked out for taps repeatedly, and every tap that
  /// did fire would extend the window.
  void _startCooldown(Duration duration) {
    _cooldownTimer?.cancel();
    state = state.copyWith(cooldownSeconds: duration.inSeconds);
    _cooldownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      final remaining = state.cooldownSeconds - 1;
      if (remaining <= 0) {
        timer.cancel();
        state = state.copyWith(cooldownSeconds: 0, clearFailure: true);
      } else {
        state = state.copyWith(cooldownSeconds: remaining);
      }
    });
  }
}

final loginControllerProvider = NotifierProvider<LoginController, LoginState>(
  LoginController.new,
);
