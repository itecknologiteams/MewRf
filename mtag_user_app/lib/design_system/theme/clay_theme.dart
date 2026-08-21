import 'package:flutter/material.dart';
import 'package:mtag_user_app/design_system/tokens/clay_metrics.dart';
import 'package:mtag_user_app/design_system/tokens/clay_palette.dart';

/// Clay tokens, reachable from any widget via [ClayTheme.of].
///
/// A [ThemeExtension] rather than a global, so a golden test can render the same
/// widget under both palettes without touching app state, and so a nested
/// [Theme] (the light-on-dark top-up sheet, for instance) resolves correctly.
@immutable
class ClayTheme extends ThemeExtension<ClayTheme> {
  const ClayTheme({required this.palette});

  final ClayPalette palette;

  /// The clay tokens in scope.
  ///
  /// `of(context)` rather than a factory constructor because that is the Flutter
  /// convention for reading an inherited value, and every caller in this codebase
  /// (and every Flutter reader) expects `Theme.of`-shaped access.
  // ignore: prefer_constructors_over_static_methods — Flutter's `of` convention.
  static ClayTheme of(BuildContext context) {
    final ext = Theme.of(context).extension<ClayTheme>();
    assert(
      ext != null,
      'No ClayTheme in scope. Every clay widget reads its colours from the '
      'theme, so a MaterialApp without clayTheme()/clayDarkTheme() applied '
      'would fall back to Material defaults and silently lose the whole visual '
      'language. Wrap with ClayApp or apply clayTheme().',
    );
    return ext ?? const ClayTheme(palette: ClayPalette.light);
  }

  @override
  ClayTheme copyWith({ClayPalette? palette}) =>
      ClayTheme(palette: palette ?? this.palette);

  @override
  ClayTheme lerp(ClayTheme? other, double t) {
    if (other == null) return this;
    return ClayTheme(palette: palette.lerpTo(other.palette, t));
  }
}

/// Font stack.
///
/// Nunito is the rounded Latin face, bundled as an asset — `google_fonts` fetches
/// at runtime and these users are on patchy mobile data or a toll LAN with no
/// internet, where a runtime fetch means the app renders in Roboto.
///
/// NotoSansArabic is the fallback, and it is not optional: Nunito has no
/// Arabic-script glyphs, so without it every Urdu string would render as tofu on
/// a device with no Arabic font and as some arbitrary system face on one that
/// has one.
const _fontFamily = 'Nunito';
const _fontFallback = <String>['NotoSansArabic'];

/// Figures that must not jitter when they change.
///
/// A balance refreshing from "1,250" to "1,180" reflows by a few pixels with
/// proportional digits, and on a hero figure at 40sp that reads as the whole
/// card twitching. Tabular figures pin every digit to the same advance width.
const _tabular = <FontFeature>[FontFeature.tabularFigures()];

TextTheme _textTheme(ClayPalette palette) {
  final primary = palette.textPrimary;
  final muted = palette.textMuted;

  return TextTheme(
    // The hero balance. Loudest thing on any screen, by a wide margin.
    displayLarge: TextStyle(
      fontSize: 40,
      fontWeight: FontWeight.w700,
      height: 1.1,
      letterSpacing: -0.5,
      color: primary,
      fontFeatures: _tabular,
    ),
    // A secondary balance — a tag card, an account row.
    displayMedium: TextStyle(
      fontSize: 28,
      fontWeight: FontWeight.w700,
      height: 1.15,
      color: primary,
      fontFeatures: _tabular,
    ),
    displaySmall: TextStyle(
      fontSize: 22,
      fontWeight: FontWeight.w700,
      height: 1.2,
      color: primary,
      fontFeatures: _tabular,
    ),
    // Screen title.
    headlineMedium: TextStyle(
      fontSize: 24,
      fontWeight: FontWeight.w700,
      height: 1.25,
      color: primary,
    ),
    // Card title.
    titleLarge: TextStyle(
      fontSize: 18,
      fontWeight: FontWeight.w700,
      height: 1.3,
      color: primary,
    ),
    titleMedium: TextStyle(
      fontSize: 16,
      fontWeight: FontWeight.w600,
      height: 1.35,
      color: primary,
    ),
    // Button label.
    labelLarge: TextStyle(
      fontSize: 16,
      fontWeight: FontWeight.w700,
      height: 1.2,
      color: primary,
    ),
    labelMedium: TextStyle(
      fontSize: 13,
      fontWeight: FontWeight.w600,
      height: 1.3,
      color: muted,
    ),
    // Smallest text in the app. 11sp at w600 so it stays legible on a low-DPI
    // budget phone, which is most of this user base.
    labelSmall: TextStyle(
      fontSize: 11,
      fontWeight: FontWeight.w600,
      height: 1.3,
      letterSpacing: 0.3,
      color: muted,
    ),
    bodyLarge: TextStyle(
      fontSize: 16,
      fontWeight: FontWeight.w400,
      height: 1.45,
      color: primary,
    ),
    bodyMedium: TextStyle(
      fontSize: 14,
      fontWeight: FontWeight.w400,
      height: 1.45,
      color: primary,
    ),
    bodySmall: TextStyle(
      fontSize: 12,
      fontWeight: FontWeight.w400,
      height: 1.4,
      color: muted,
    ),
  ).apply(fontFamily: _fontFamily, fontFamilyFallback: _fontFallback);
}

ThemeData _theme(ClayPalette palette) {
  final text = _textTheme(palette);
  return ThemeData(
    useMaterial3: true,
    brightness: palette.isDark ? Brightness.dark : Brightness.light,
    fontFamily: _fontFamily,
    fontFamilyFallback: _fontFallback,
    scaffoldBackgroundColor: palette.base,
    canvasColor: palette.base,
    textTheme: text,
    // Dividers are now part of the system rather than banned from it: this design
    // separates with hairlines, so a rule inside a card is the same language as the
    // border around it. Themed centrally so every one of them matches the borders
    // exactly — a divider a shade off from the card edge is worse than none.
    dividerTheme: DividerThemeData(
      color: palette.border,
      thickness: 1,
      space: 1,
    ),
    splashFactory: NoSplash.splashFactory,
    highlightColor: Colors.transparent,
    hoverColor: Colors.transparent,
    colorScheme:
        ColorScheme.fromSeed(
          seedColor: palette.primary,
          brightness: palette.isDark ? Brightness.dark : Brightness.light,
        ).copyWith(
          primary: palette.primary,
          onPrimary: palette.onPrimary,
          surface: palette.surface,
          onSurface: palette.textPrimary,
          error: palette.danger,
        ),
    extensions: [ClayTheme(palette: palette)],
  );
}

ThemeData clayLightTheme() => _theme(ClayPalette.light);

ThemeData clayDarkTheme() => _theme(ClayPalette.dark);

/// Whether to drop shimmer and press animations.
///
/// Respects the platform reduce-motion setting. The DEPTH always stays — depth is
/// the information architecture here, not decoration, and removing it would leave
/// a screen of borderless grey blocks with nothing separating them.
bool clayReduceMotion(BuildContext context) =>
    MediaQuery.disableAnimationsOf(context);

/// Press duration, or zero when motion is reduced.
Duration clayPressDuration(BuildContext context) =>
    clayReduceMotion(context) ? Duration.zero : ClayMotion.press;

/// Any duration, collapsed to zero when the platform asks for reduced motion.
///
/// Every animated widget in the app routes its duration through this. Reduce-motion is an
/// accessibility setting people turn on because motion makes them ill — honouring it
/// halfway, so most things animate but a few still slide, is worse than not honouring it
/// at all.
Duration clayDuration(BuildContext context, Duration duration) =>
    clayReduceMotion(context) ? Duration.zero : duration;
