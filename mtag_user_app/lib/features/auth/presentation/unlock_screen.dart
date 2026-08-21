import 'dart:io' show Platform;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/auth/data/biometric_service.dart';
import 'package:mtag_user_app/features/auth/presentation/biometric_gate.dart';
import 'package:mtag_user_app/features/auth/presentation/session_controller.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// The biometric unlock screen.
///
/// Shown instead of the dashboard when a valid session exists and biometric unlock is on.
/// The prompt fires automatically on arrival — making the user tap a button to reach a system
/// sheet they were expecting anyway is pure friction — and the button remains for retries.
///
/// Platform parity is in the LABEL and ICON, not the mechanism: `local_auth` drives Face ID
/// on iOS and BiometricPrompt on Android, and this screen names whichever the hardware
/// actually offers. Telling an iPhone user to "use your fingerprint" makes a working feature
/// look broken.
class UnlockScreen extends ConsumerStatefulWidget {
  const UnlockScreen({super.key});

  @override
  ConsumerState<UnlockScreen> createState() => _UnlockScreenState();
}

class _UnlockScreenState extends ConsumerState<UnlockScreen> {
  String? _message;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    // Post-frame: the prompt is a platform sheet and must not be raised during the first
    // build of the route that hosts it.
    WidgetsBinding.instance.addPostFrameCallback((_) => _prompt());
  }

  Future<void> _prompt() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _message = null;
    });

    final l10n = AppL10n.of(context);
    final result = await ref
        .read(biometricGateProvider.notifier)
        .unlock(reason: l10n.unlockReason);

    if (!mounted) return;
    setState(() {
      _busy = false;
      _message = switch (result) {
        BiometricAuthResult.success => null,
        // A dismissed sheet needs no scolding — the retry button is right there.
        BiometricAuthResult.cancelled => null,
        BiometricAuthResult.failed => l10n.unlockFailed,
        BiometricAuthResult.lockedOut => l10n.unlockLockedOut,
        BiometricAuthResult.unavailable ||
        BiometricAuthResult.misconfigured => null,
      };
    });
  }

  Future<void> _usePassword() async {
    // Signing out is the honest action behind "use password instead": the session is what
    // the gate protects, so keeping it alive while dropping the gate would leave the wallet
    // reachable by anyone holding the phone.
    ref.read(biometricGateProvider.notifier).bypassToPassword();
    await ref.read(sessionControllerProvider.notifier).signOut();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;
    final kind = ref.watch(biometricGateProvider).value?.kind ?? _defaultKind();

    final (IconData icon, String label) = switch (kind) {
      BiometricKind.face => (Icons.face_rounded, l10n.unlockFace),
      BiometricKind.fingerprint => (
        Icons.fingerprint_rounded,
        l10n.unlockFingerprint,
      ),
      BiometricKind.iris ||
      BiometricKind.generic ||
      BiometricKind.none => (Icons.lock_open_rounded, l10n.unlockGeneric),
    };

    return Scaffold(
      backgroundColor: palette.base,
      body: ClayAmbient(
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(ClaySpace.xxl),
            child: Column(
              children: [
                const Spacer(flex: 3),

                Image.asset(
                  palette.isDark
                      ? 'assets/images/logo_dark.png'
                      : 'assets/images/logo_light.png',
                  width: 190,
                  fit: BoxFit.contain,
                  excludeFromSemantics: true,
                ),
                const SizedBox(height: ClaySpace.xl),
                Text(l10n.unlockTitle, style: textTheme.headlineMedium),
                const SizedBox(height: ClaySpace.xs),
                Text(
                  l10n.unlockSubtitle,
                  style: textTheme.bodySmall,
                  textAlign: TextAlign.center,
                ),

                const Spacer(flex: 2),

                // The glass biometric target. Large and centred because it is the only
                // thing to do on this screen.
                GestureDetector(
                  onTap: _busy ? null : _prompt,
                  child: ClaySurface(
                    radius: ClayRadius.pill,
                    depth: ClayDepth.hero,
                    borderColor: palette.primary.withValues(alpha: 0.4),
                    width: 116,
                    height: 116,
                    child: Center(
                      child: _busy
                          ? SizedBox(
                              width: 30,
                              height: 30,
                              child: CircularProgressIndicator(
                                strokeWidth: 2.4,
                                valueColor: AlwaysStoppedAnimation(
                                  palette.primary,
                                ),
                              ),
                            )
                          : Icon(icon, size: 52, color: palette.primary),
                    ),
                  ),
                ),
                const SizedBox(height: ClaySpace.lg),
                Text(label, style: textTheme.titleMedium),

                if (_message != null) ...[
                  const SizedBox(height: ClaySpace.lg),
                  Text(
                    _message!,
                    style: textTheme.bodySmall?.copyWith(
                      color: palette.dangerOnSurface,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ],

                const Spacer(flex: 3),

                ClayButton(
                  label: l10n.unlockUsePassword,
                  variant: ClayButtonVariant.ghost,
                  expand: true,
                  onPressed: _usePassword,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// Before the gate resolves, guess from the platform so the icon does not flip.
  static BiometricKind _defaultKind() =>
      Platform.isIOS ? BiometricKind.face : BiometricKind.fingerprint;
}
