import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/storage/secure_store.dart' show SecureStore;
import 'package:shared_preferences/shared_preferences.dart';

/// Theme and locale.
///
/// `SharedPreferences`, not secure storage — this is a display preference, and
/// nothing here is worth encrypting. Anything sensitive goes to [SecureStore].
class AppSettings {
  /// Defaults to DARK, not `ThemeMode.system`.
  ///
  /// The design is dark-premium: near-black ground, glass panels lit by an orange ambient
  /// glow. That is the app's identity, not a night-time accommodation, and following the
  /// system would show half the users a light theme that the material was never tuned for
  /// — glass over white has almost nothing to be translucent against. Light is fully
  /// supported and one tap away in Profile.
  const AppSettings({this.themeMode = ThemeMode.dark, this.locale});

  final ThemeMode themeMode;

  /// Null means follow the platform. Both themes and both languages are
  /// first-class; the manual override in Profile is for the many users whose phone
  /// is set to English but who read Urdu, and vice versa.
  final Locale? locale;

  AppSettings copyWith({
    ThemeMode? themeMode,
    Locale? locale,
    bool clearLocale = false,
  }) => AppSettings(
    themeMode: themeMode ?? this.themeMode,
    locale: clearLocale ? null : (locale ?? this.locale),
  );
}

class AppSettingsController extends Notifier<AppSettings> {
  static const _themeKey = 'mtag_theme_mode';
  static const _localeKey = 'mtag_locale';

  SharedPreferences? _prefs;

  @override
  AppSettings build() {
    // Loaded asynchronously after the first frame. Light is what a new install gets and
    // what the user sees for the few milliseconds before a stored choice arrives — a
    // blocking read here would delay the first frame to avoid a flash that only affects
    // people who overrode the default.
    Future.microtask(_load);
    return const AppSettings();
  }

  Future<void> _load() async {
    final prefs = _prefs ??= await SharedPreferences.getInstance();
    final theme = prefs.getString(_themeKey);
    final locale = prefs.getString(_localeKey);
    state = AppSettings(
      themeMode: switch (theme) {
        'light' => ThemeMode.light,
        'system' => ThemeMode.system,
        // Anything else, including an unset preference, is dark.
        _ => ThemeMode.dark,
      },
      locale: (locale == null || locale.isEmpty) ? null : Locale(locale),
    );
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    state = state.copyWith(themeMode: mode);
    final prefs = _prefs ??= await SharedPreferences.getInstance();
    await prefs.setString(_themeKey, mode.name);
  }

  /// Null restores "follow the phone".
  Future<void> setLocale(Locale? locale) async {
    state = state.copyWith(locale: locale, clearLocale: locale == null);
    final prefs = _prefs ??= await SharedPreferences.getInstance();
    if (locale == null) {
      await prefs.remove(_localeKey);
    } else {
      await prefs.setString(_localeKey, locale.languageCode);
    }
  }
}

final appSettingsProvider =
    NotifierProvider<AppSettingsController, AppSettings>(
      AppSettingsController.new,
    );
