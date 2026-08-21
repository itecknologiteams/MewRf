import 'dart:io' show Platform;

import 'package:flutter/services.dart';
import 'package:local_auth/local_auth.dart';

/// What kind of biometric the device offers, so the UI can name it correctly.
///
/// Calling a Face ID prompt "fingerprint" on an iPhone, or vice versa, makes a security
/// affordance look broken — the user is told to do something the hardware cannot do.
enum BiometricKind { fingerprint, face, iris, generic, none }

/// Biometric capability and prompting.
///
/// ## What biometric login can and cannot mean here
///
/// The backend authenticates **phone + password** and nothing else. A fingerprint cannot be
/// presented to it, so "biometric login" cannot mean authenticating to the server.
///
/// What it does mean: the session lives in an httpOnly cookie jar with a 7-day refresh
/// token, so after one password login the app already holds a usable session. Biometrics
/// gate access to THAT — the same model most banking apps use. Concretely:
///
///   * password login once, then opt in;
///   * on later cold starts, a fingerprint (or Face ID) reveals the app;
///   * if the session has since expired, the password screen returns with an explanation.
///
/// **No password is ever stored.** Persisting one to replay at login is the usual shortcut
/// and it would turn a stolen phone into a stolen account — the keystore protects it from
/// other apps, not from someone holding an unlocked device.
class BiometricService {
  BiometricService({LocalAuthentication? auth})
    : _auth = auth ?? LocalAuthentication();

  final LocalAuthentication _auth;

  /// Whether the device has hardware AND an enrolled biometric.
  ///
  /// Both matter: hardware with nothing enrolled makes every prompt fail instantly, which
  /// reads as the app being broken rather than as a setup step the user has not done.
  Future<bool> get isAvailable async {
    try {
      final supported = await _auth.isDeviceSupported();
      if (!supported) return false;
      return _auth.canCheckBiometrics;
    } on PlatformException {
      // A platform without the plugin, or an OEM that throws instead of returning false.
      // Absent capability is not an error worth surfacing.
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  /// The strongest enrolled modality, for naming and iconography.
  Future<BiometricKind> get kind async {
    try {
      final available = await _auth.getAvailableBiometrics();
      if (available.isEmpty) return BiometricKind.none;
      if (available.contains(BiometricType.face)) return BiometricKind.face;
      if (available.contains(BiometricType.fingerprint)) {
        return BiometricKind.fingerprint;
      }
      if (available.contains(BiometricType.iris)) return BiometricKind.iris;

      // iOS reports `strong`/`weak` rather than the modality on some versions. The platform
      // still tells us which hardware exists, and on iOS a strong biometric is Face ID on
      // every current device except the SE line.
      if (Platform.isIOS) return BiometricKind.face;
      return BiometricKind.generic;
    } on PlatformException {
      return BiometricKind.none;
    } on MissingPluginException {
      return BiometricKind.none;
    }
  }

  /// Prompts, returning true only on a positive match.
  ///
  /// `biometricOnly` is deliberate: falling back to the device PIN would mean anyone who can
  /// unlock the phone can open a payment app, which defeats the point of the gate.
  Future<BiometricAuthResult> authenticate({required String reason}) async {
    try {
      final ok = await _auth.authenticate(
        localizedReason: reason,
        options: const AuthenticationOptions(
          biometricOnly: true,
          stickyAuth: true,
        ),
      );
      return ok ? BiometricAuthResult.success : BiometricAuthResult.cancelled;
    } on PlatformException catch (error) {
      // Distinguished so the UI can say something useful. `lockedOut` in particular must not
      // read as "your fingerprint is wrong" — the sensor is refusing everyone for a while.
      return switch (error.code) {
        'LockedOut' || 'PermanentlyLockedOut' => BiometricAuthResult.lockedOut,
        'NotEnrolled' || 'NotAvailable' => BiometricAuthResult.unavailable,
        'no_fragment_activity' => BiometricAuthResult.misconfigured,
        _ => BiometricAuthResult.failed,
      };
    } on MissingPluginException {
      return BiometricAuthResult.unavailable;
    }
  }
}

enum BiometricAuthResult {
  success,

  /// The user dismissed the sheet. Not an error — no message needed.
  cancelled,

  /// Presented but did not match.
  failed,

  /// Too many attempts; the sensor is refusing everyone temporarily.
  lockedOut,

  /// No hardware, or nothing enrolled.
  unavailable,

  /// The host Activity is not a FragmentActivity. A build error, not a user error — see
  /// MainActivity.kt.
  misconfigured,
}
