import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/features/auth/data/biometric_service.dart';

final biometricServiceProvider = Provider<BiometricService>(
  (ref) => BiometricService(),
);

/// Whether the app is currently held behind a biometric prompt.
///
/// ## Why this exists
///
/// The Profile toggle previously wrote a preference that **nothing ever read**. A user could
/// turn on "Unlock with biometrics", be told it was on, and never once be asked for a
/// fingerprint. A security setting that silently does nothing is worse than not offering it,
/// because the user changes their behaviour on the strength of it.
///
/// ## Why a lock rather than a login
///
/// The backend authenticates phone + password only; a fingerprint cannot be presented to it.
/// But the session already persists in the cookie jar for 7 days, so on a warm start the
/// app holds a working session and the cold-start probe would walk straight in. This gate
/// deliberately holds that back until the biometric passes — which is the only thing
/// "biometric login" can honestly mean here, and is the same model banking apps use.
///
/// Unlock state is per-launch and in memory only. Persisting it would mean a stolen phone
/// stays unlocked, which is the case the gate exists for.
class BiometricGate extends AsyncNotifier<BiometricGateState> {
  @override
  Future<BiometricGateState> build() async {
    final enabled = await ref
        .read(secureStoreProvider)
        .readBiometricLockEnabled();
    if (!enabled) return const BiometricGateState.notRequired();

    // Enabled in preferences but the device has since lost its enrolment (biometrics
    // removed, or the app restored onto different hardware). Locking the user out of their
    // own wallet over a setting would be indefensible, so the gate opens and Profile will
    // show the capability as unavailable.
    final available = await ref.read(biometricServiceProvider).isAvailable;
    if (!available) return const BiometricGateState.notRequired();

    final kind = await ref.read(biometricServiceProvider).kind;
    return BiometricGateState.locked(kind);
  }

  /// Runs the prompt. Returns the outcome so the UI can explain a failure.
  Future<BiometricAuthResult> unlock({required String reason}) async {
    final result = await ref
        .read(biometricServiceProvider)
        .authenticate(reason: reason);

    if (result == BiometricAuthResult.success) {
      state = const AsyncValue.data(BiometricGateState.unlocked());
    } else if (result == BiometricAuthResult.unavailable ||
        result == BiometricAuthResult.misconfigured) {
      // The gate cannot be satisfied on this device. Opening it is the only option that does
      // not strand the user; the alternative is an unusable app.
      state = const AsyncValue.data(BiometricGateState.notRequired());
    }
    return result;
  }

  /// Escape hatch: sign out and use the password instead.
  void bypassToPassword() {
    state = const AsyncValue.data(BiometricGateState.notRequired());
  }

  /// Re-locks on the next launch. Called after sign-out so the next user of the device is
  /// not handed an unlocked session.
  void relock() => ref.invalidateSelf();
}

final biometricGateProvider =
    AsyncNotifierProvider<BiometricGate, BiometricGateState>(
      BiometricGate.new,
    );

class BiometricGateState {
  const BiometricGateState._(this.isLocked, this.kind);

  /// Not enabled, or not satisfiable on this device.
  const BiometricGateState.notRequired() : this._(false, BiometricKind.none);

  const BiometricGateState.locked(BiometricKind kind) : this._(true, kind);

  const BiometricGateState.unlocked() : this._(false, BiometricKind.none);

  final bool isLocked;
  final BiometricKind kind;
}
