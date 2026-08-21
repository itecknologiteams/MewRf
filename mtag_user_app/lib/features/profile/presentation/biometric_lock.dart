import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:local_auth/local_auth.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Optional biometric app lock.
///
/// **A local gate, not authentication.** The session lives in httpOnly cookies and this
/// does nothing to them — it only decides whether the app's own UI is shown. Anyone who
/// can read the app's private storage bypasses it entirely, which is why it is offered as
/// convenience-grade privacy (a shared handset, a phone handed to a mechanic) and never
/// described as security.
///
/// Off by default: turning it on for a user whose device has no enrolled biometric would
/// lock them out of their own wallet, and this is a wallet people open at a barrier.
class BiometricLockCard extends ConsumerStatefulWidget {
  const BiometricLockCard({super.key});

  @override
  ConsumerState<BiometricLockCard> createState() => _BiometricLockCardState();
}

class _BiometricLockCardState extends ConsumerState<BiometricLockCard> {
  final _auth = LocalAuthentication();

  bool _enabled = false;
  bool _available = false;
  bool _checked = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final enabled = await ref
        .read(secureStoreProvider)
        .readBiometricLockEnabled();
    var available = false;
    try {
      available =
          await _auth.canCheckBiometrics && await _auth.isDeviceSupported();
    } on Object {
      // A platform that does not implement local_auth, or a device with the API
      // disabled. Treated as unavailable rather than crashing the profile screen.
      available = false;
    }
    if (!mounted) return;
    setState(() {
      _enabled = enabled;
      _available = available;
      _checked = true;
    });
  }

  Future<void> _toggle(bool value) async {
    final l10n = AppL10n.of(context);

    if (value) {
      // Prove the biometric works BEFORE persisting the setting. Storing it first and
      // discovering on next launch that no fingerprint is enrolled would lock the user
      // out of their own balance.
      var ok = false;
      try {
        ok = await _auth.authenticate(
          localizedReason: l10n.profileBiometricPrompt,
          options: const AuthenticationOptions(
            biometricOnly: true,
            stickyAuth: true,
          ),
        );
      } on Object {
        ok = false;
      }
      if (!ok) {
        if (mounted) {
          showClaySnack(
            context,
            message: l10n.profileBiometricUnavailable,
            tone: ClayTone.warning,
          );
        }
        return;
      }
    }

    await ref
        .read(secureStoreProvider)
        .writeBiometricLockEnabled(enabled: value);
    if (mounted) setState(() => _enabled = value);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;

    if (!_checked) return const ClaySkeletonCard(lines: 2, height: 92);

    return ClayCard(
      child: Row(
        children: [
          Icon(
            Icons.fingerprint_rounded,
            size: 22,
            color: _available ? palette.primaryOnSurface : palette.textMuted,
          ),
          const SizedBox(width: ClaySpace.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l10n.profileBiometricLock, style: textTheme.titleMedium),
                const SizedBox(height: 2),
                Text(
                  _available
                      ? l10n.profileBiometricLockSubtitle
                      : l10n.profileBiometricUnavailable,
                  style: textTheme.bodySmall,
                ),
              ],
            ),
          ),
          const SizedBox(width: ClaySpace.md),
          _ClaySwitch(
            value: _enabled,
            enabled: _available,
            onChanged: _toggle,
          ),
        ],
      ),
    );
  }
}

class _ClaySwitch extends StatelessWidget {
  const _ClaySwitch({
    required this.value,
    required this.onChanged,
    this.enabled = true,
  });

  final bool value;
  final bool enabled;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    return Semantics(
      toggled: value,
      enabled: enabled,
      child: GestureDetector(
        onTap: enabled ? () => onChanged(!value) : null,
        child: Opacity(
          opacity: enabled ? 1 : 0.5,
          child: ClaySurface(
            style: ClayDepthStyle.pressed,
            depth: ClayDepth.nested,
            radius: ClayRadius.pill,
            width: 48,
            height: 27,
            child: AnimatedAlign(
              duration: clayPressDuration(context),
              alignment: value ? Alignment.centerRight : Alignment.centerLeft,
              child: Padding(
                padding: const EdgeInsets.all(3),
                child: ClaySurface(
                  depth: ClayDepth.nested,
                  radius: ClayRadius.pill,
                  width: 21,
                  height: 21,
                  color: value ? palette.primary : palette.surface,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
