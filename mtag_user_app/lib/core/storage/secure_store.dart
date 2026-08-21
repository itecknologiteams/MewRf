import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Keychain / EncryptedSharedPreferences.
///
/// Only two things live here, and neither is a token — the session is the cookie
/// jar. `SharedPreferences` is plain-text XML on Android and is used for theme and
/// locale only.
///
/// ## Every read here can fail, and none of them may throw
///
/// The plugin keeps ciphertext in SharedPreferences and its key in the Android Keystore.
/// Android auto-backup includes the former and never the latter, so restoring a backup onto
/// a new phone — the ordinary way people change handsets — leaves data that no key on the
/// device can decrypt, and the read throws `BadPaddingException: BAD_DECRYPT`.
///
/// Neither value stored here is worth an exception. A remembered phone number is a
/// convenience, and a biometric preference has a safe default of "off". So a failed read
/// degrades to "not set" and a failed write is dropped, which costs the user one retyped
/// phone number instead of a screen that will not load.
class SecureStore {
  const SecureStore({
    FlutterSecureStorage storage = const FlutterSecureStorage(
      aOptions: AndroidOptions(resetOnError: true),
    ),
  }) : _storage = storage;

  final FlutterSecureStorage _storage;

  static const _rememberedPhone = 'mtag_remembered_phone';
  static const _biometricLock = 'mtag_biometric_lock';

  /// The phone number prefilled on the login screen.
  ///
  /// Secure rather than plain storage because it is a personal identifier tied to a
  /// toll account, and on a rooted or shared device a plain-text file naming the
  /// account holder is worth more to an attacker than it looks.
  Future<String?> readRememberedPhone() => _read(_rememberedPhone);

  Future<void> writeRememberedPhone(String phone) =>
      _write(_rememberedPhone, phone);

  Future<void> clearRememberedPhone() => _delete(_rememberedPhone);

  /// Defaults to FALSE on any failure, which is the safe direction.
  ///
  /// Reading a corrupt store as "locked" would leave the user staring at a biometric prompt
  /// they can never satisfy, with the wallet behind it; reading it as "unlocked" only costs
  /// a convenience the user can turn back on.
  Future<bool> readBiometricLockEnabled() async =>
      await _read(_biometricLock) == 'true';

  Future<void> writeBiometricLockEnabled({required bool enabled}) =>
      _write(_biometricLock, enabled.toString());

  Future<String?> _read(String key) async {
    try {
      return await _storage.read(key: key);
    } on Object {
      // Broad on purpose: the failure crosses a platform channel and arrives as whatever
      // the host threw. Narrowing it to PlatformException would let a different Keystore
      // fault propagate into a screen that cannot handle it.
      return null;
    }
  }

  Future<void> _write(String key, String value) async {
    try {
      await _storage.write(key: key, value: value);
    } on Object {
      // Dropped. A preference that fails to persist is a preference the user sets again.
    }
  }

  Future<void> _delete(String key) async {
    try {
      await _storage.delete(key: key);
    } on Object {
      // Nothing to do — and a failed delete of a value that cannot be READ either is
      // already inert.
    }
  }
}
