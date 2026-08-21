import 'dart:io';

import 'package:cookie_jar/cookie_jar.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';

/// The cookie jar. This IS the session.
///
/// `LoginView` pops `access` and `refresh` out of the response body and sets them
/// as httpOnly cookies, and `TokenRefreshCookieView` reads the refresh token
/// **only** from `request.COOKIES` — never from the body. So there is no token for
/// the client to hold: possession of these two cookies is the entire auth state.
/// Losing the jar is logging out; persisting it is staying logged in.
///
/// Hence [PersistCookieJar] on disk. A plain in-memory `CookieJar` would look
/// perfectly correct in every test and log the user out on every cold start.
class CookieStore {
  CookieStore._(this.jar, this._directory);

  static const _keyAlias = 'mtag_cookie_jar_key';
  static const _dirName = 'mtag_cookies';

  final PersistCookieJar jar;
  final Directory _directory;

  /// `resetOnError` is belt to the braces of [_ensureKey]'s own recovery below.
  ///
  /// The plugin keeps its data in SharedPreferences and its key in the Android Keystore.
  /// Those two are backed up differently — the prefs file is included in Android
  /// auto-backup, the Keystore key is NOT — so a restored backup, and some reinstalls, leave
  /// ciphertext that no key on the device can open.
  static const _androidOptions = AndroidOptions(resetOnError: true);

  static Future<CookieStore> open({
    FlutterSecureStorage secureStorage = const FlutterSecureStorage(
      aOptions: _androidOptions,
    ),
  }) async {
    final support = await getApplicationSupportDirectory();
    final dir = Directory('${support.path}/$_dirName');
    if (!dir.existsSync()) {
      await dir.create(recursive: true);
    }

    // The jar files themselves are plain JSON in app-private storage, which is
    // already inaccessible to other apps on a non-rooted device. The secure-store
    // entry is the app-lifetime marker: it lives in the Keychain / EncryptedSharedPreferences,
    // survives with the install, and is wiped by the OS when the app is removed —
    // so a reinstall cannot resurrect a jar left behind on disk.
    final key = await _ensureKey(secureStorage);

    final jar = PersistCookieJar(
      storage: FileStorage(dir.path),
    );
    final store = CookieStore._(jar, dir);

    // The marker could not be read, so this install's provenance is unknown. A jar left on
    // disk from a previous install must not be adopted — that is the exact thing the marker
    // exists to prevent — so it is dropped and the user simply signs in again.
    if (key == null) {
      await store.clear();
    }
    return store;
  }

  /// The install marker, or null if it had to be reset.
  ///
  /// MUST NOT THROW. It is awaited by `main()` before `runApp`, so an exception here is not
  /// an error the user can see or act on — it is an app that never paints a frame and sits
  /// on the native splash forever. That is exactly what shipped: a `PlatformException`
  /// carrying `javax.crypto.BadPaddingException: BAD_DECRYPT` from a Keystore key that no
  /// longer matched the stored ciphertext, and the app was bricked with no way out but
  /// clearing app data — which no ordinary user knows to do.
  ///
  /// The decrypt failure is not exotic. `flutter_secure_storage` stores ciphertext in
  /// SharedPreferences and its key in the Android Keystore; Android auto-backup includes the
  /// former and never the latter. So any user who restores a backup onto a new phone — the
  /// normal way people move to a new handset — lands on undecryptable data.
  ///
  /// Recovery is to throw the marker away and start clean. There is nothing of value in it:
  /// it is an opaque token whose only job is to say "this install wrote that jar".
  static Future<String?> _ensureKey(FlutterSecureStorage storage) async {
    try {
      final existing = await storage.read(key: _keyAlias);
      if (existing != null) return existing;
    } on Object {
      // Deliberately catching everything, not just PlatformException: the failure crosses a
      // platform channel and arrives as whatever the host chose to throw. Being precise here
      // would mean a different Keystore fault re-bricks the app.
      try {
        await storage.delete(key: _keyAlias);
      } on Object {
        // Even the delete can fail on a wedged Keystore. Fall through and write over it.
      }
      await _write(storage);
      return null;
    }
    await _write(storage);
    return null;
  }

  static Future<void> _write(FlutterSecureStorage storage) async {
    try {
      await storage.write(
        key: _keyAlias,
        value: DateTime.now().microsecondsSinceEpoch.toRadixString(36),
      );
    } on Object {
      // A device whose Keystore refuses writes still gets a working app; it just cannot
      // tell one install from the next, which costs a sign-in, not a session.
    }
  }

  /// Whether a session cookie is present for [origin].
  ///
  /// Only ever a hint for the splash screen — it says a cookie EXISTS, not that it
  /// is valid. `CookieJWTAuthentication` treats an unusable cookie as anonymous
  /// rather than as an error, so a stale jar produces a 401 from the permission
  /// layer, not a crash. The real session probe is `GET /auth/me/`.
  Future<bool> hasSessionCookie(Uri origin) async {
    final cookies = await jar.loadForRequest(origin);
    return cookies.any(
      (c) => c.name == 'refresh_token' || c.name == 'access_token',
    );
  }

  /// Drops the whole session.
  ///
  /// Called on logout and whenever a refresh fails. Deleting the files as well as
  /// clearing memory matters: `PersistCookieJar` writes lazily, and a jar cleared
  /// in memory but left on disk comes back on the next launch.
  Future<void> clear() async {
    await jar.deleteAll();
    if (_directory.existsSync()) {
      for (final entity in _directory.listSync()) {
        try {
          entity.deleteSync(recursive: true);
        } on FileSystemException {
          // A file the OS still has open is not worth failing a logout over; the
          // in-memory jar is already empty, so the session is gone either way.
        }
      }
    }
  }
}
