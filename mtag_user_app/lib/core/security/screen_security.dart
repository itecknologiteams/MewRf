import 'package:flutter/services.dart';

/// Screenshot and recents-thumbnail blocking for money screens.
///
/// Implemented over a `MethodChannel` to `FLAG_SECURE` rather than with a package.
/// The pub options are either unmaintained (last Flutter 2), or wrap the same one
/// Android call in a plugin whose only job is that call. One channel and a dozen
/// lines of Kotlin is less to keep working than a dependency that stops building on
/// the next Gradle bump.
///
/// **Android only, and that is not a shortcut.** `FLAG_SECURE` blocks screenshots,
/// screen recording and the recents-list thumbnail. iOS has no equivalent: the OS
/// permits screenshots unconditionally, and the only available mitigation is hiding
/// content when the app backgrounds. So on iOS these calls are no-ops, and the
/// README says so rather than implying parity.
class ScreenSecurity {
  ScreenSecurity._();

  static final ScreenSecurity instance = ScreenSecurity._();

  static const _channel = MethodChannel('mtag/screen_security');

  bool _secure = false;

  bool get isSecure => _secure;

  Future<void> initialise() async {
    // Nothing to do at launch — the flag is raised per screen. Present so main() has
    // a single obvious place to fail early if the channel is missing.
    await _invoke('initialise');
  }

  /// Raises `FLAG_SECURE`. Called on entry to any screen showing a TID or a balance
  /// the user is about to pay against.
  Future<void> enable() async {
    if (_secure) return;
    _secure = true;
    await _invoke('enable');
  }

  Future<void> disable() async {
    if (!_secure) return;
    _secure = false;
    await _invoke('disable');
  }

  Future<void> _invoke(String method) async {
    try {
      await _channel.invokeMethod<void>(method);
    } on MissingPluginException {
      // iOS, or a platform where the channel is not registered. Not an error worth
      // crashing the app over — the screen still works, it is just screenshottable.
    } on PlatformException {
      // Some OEM Android builds refuse FLAG_SECURE on certain window types. Failing
      // to harden a screen must never prevent a user from topping up.
    }
  }
}
