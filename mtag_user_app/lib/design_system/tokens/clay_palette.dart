import 'package:flutter/material.dart';

/// The colour palette. **Dark is the design; light is a supported alternate.**
///
/// Built to a 70 / 20 / 10 split:
///   * **70%** near-black ground — #050505 page, #151515 surface, #1D1D1D elevated.
///   * **20%** white and grey content — #FFFFFF primary text, #A3A3A3 secondary.
///   * **10%** Expressway Orange #FF8500, from the M-E mark. It is an ACCENT: the primary
///     action, the active state, the ambient glow behind glass. The moment it starts
///     filling large areas the ratio is gone and so is the premium read.
///
/// Measured contrast on `surface` #151515 — everything clears WCAG AA, most clear AAA:
///   textPrimary  #FFFFFF  18.1:1  ✓ AAA
///   textMuted    #A3A3A3   7.2:1  ✓ AAA
///   primary      #FF8500   7.5:1  ✓ AAA   — orange is legible as TEXT here, unusually
///   success      #32D583   9.6:1  ✓ AAA
///   warning      #FFB020  10.4:1  ✓ AAA
///   danger       #FF4D4F   5.6:1  ✓ AA
///
/// A dark ground is what buys that: the same orange was only 3.9:1 on white, which is why
/// the light palette below darkens it to #E06E00 for text rather than reusing #FF8500.
///
/// Colour still never carries meaning alone — every status colour is paired with an icon
/// or a label.
@immutable
class ClayPalette {
  const ClayPalette({
    required this.base,
    required this.surface,
    required this.border,
    required this.borderStrong,
    required this.elevated,
    required this.glassFill,
    required this.glassFillStrong,
    required this.glow,
    required this.highlight,
    required this.shadow,
    required this.primary,
    required this.primarySoft,
    required this.primaryOnSurface,
    required this.success,
    required this.successOnSurface,
    required this.warning,
    required this.warningOnSurface,
    required this.danger,
    required this.dangerOnSurface,
    required this.onPrimary,
    required this.textPrimary,
    required this.textMuted,
    required this.isDark,
  });

  /// Page background.
  final Color base;

  /// Card fill — pure white, so a card reads as a sheet laid on the page.
  final Color surface;

  /// The hairline that defines a card's edge.
  ///
  /// This is what carries the structure now. A 1px border states exactly where a surface
  /// ends, which a shadow can only imply — and it stays legible on a cheap panel, at any
  /// brightness, and for anyone who cannot resolve a soft gradient.
  final Color border;

  /// A heavier rule, for a divider inside a card or a selected outline.
  final Color borderStrong;

  /// One step above [surface] — a sheet, a menu, a selected row.
  final Color elevated;

  /// The translucent wash that makes a glass panel.
  ///
  /// Deliberately low alpha: glass reads as glass because you can see the ambient glow
  /// THROUGH it, so a fill opaque enough to be comfortable on its own has already stopped
  /// being glass.
  final Color glassFill;

  /// A heavier wash, for glass that has to carry small text (a transaction row).
  final Color glassFillStrong;

  /// The ambient light behind the glass.
  ///
  /// Without this the whole effect collapses: a backdrop blur over a flat #050505 field
  /// blurs nothing and costs a full-screen save layer for a result identical to a plain
  /// translucent fill. The glow is what there is to see through the panel.
  final Color glow;

  /// Retained for the few places that still want a light edge (the pressed input's inner
  /// top highlight). Not used for card elevation any more.
  final Color highlight;

  /// The single drop shadow under a raised surface. Already carries its own opacity, and
  /// deliberately faint — the border defines the edge, the shadow only lifts it.
  final Color shadow;

  final Color primary;
  final Color primarySoft;

  /// [primary] darkened enough to be small text on [surface].
  final Color primaryOnSurface;

  final Color success;
  final Color successOnSurface;
  final Color warning;
  final Color warningOnSurface;
  final Color danger;
  final Color dangerOnSurface;

  /// Text/icon colour to use on top of a [primary]/[success]/[danger] fill.
  final Color onPrimary;

  final Color textPrimary;
  final Color textMuted;

  final bool isDark;

  /// LIGHT — the default.
  ///
  /// Soft UI rather than heavy clay: the card is near-WHITE and the page behind it is a
  /// cool light grey, so a surface separates by being visibly lighter than its ground
  /// rather than by casting a large shadow. That is what lets the shadows stay tight and
  /// subtle (see ClaySurface) without the layout turning into mush.
  ///
  /// The near-white surface also buys contrast: every content colour measures BETTER on
  /// #FBFCFE than it did on the old #EEF1F8.
  ///
  /// Contrast on `surface` #FBFCFE:
  ///   textPrimary       #2B3550  11.84:1  ✓ AA
  ///   textMuted         #5F6B8A   5.15:1  ✓ AA   (spec #7C88A8 was 3.13:1)
  ///   primaryOnSurface  #1B5FCB   5.77:1  ✓ AA
  ///   successOnSurface  #0E7A52   5.21:1  ✓ AA
  ///   warningOnSurface  #8A5300   6.16:1  ✓ AA
  ///   dangerOnSurface   #C4304A   5.29:1  ✓ AA
  /// Fill colours, for reference — usable as fills/icons/large figures only:
  ///   primary #2E7DF6 3.80:1 · danger #F0526B 3.34:1 · success #3BC98C 2.06:1
  static const light = ClayPalette(
    base: Color(0xFFF5F7FA),
    surface: Color(0xFFFFFFFF),
    elevated: Color(0xFFFFFFFF),
    border: Color(0xFFE3E8EF),
    borderStrong: Color(0xFFD0D7E2),
    glassFill: Color(0xB3FFFFFF),
    glassFillStrong: Color(0xE6FFFFFF),
    glow: Color(0x1AFF8500),
    highlight: Color(0xFFFFFFFF),
    shadow: Color(0x14101828),
    primary: Color(0xFFE06E00),
    primarySoft: Color(0xFFFFF1E0),
    primaryOnSurface: Color(0xFFB35400),
    success: Color(0xFF12A150),
    successOnSurface: Color(0xFF0E7A52),
    warning: Color(0xFFB26A00),
    warningOnSurface: Color(0xFF8A5300),
    danger: Color(0xFFE5484D),
    dangerOnSurface: Color(0xFFC4304A),
    onPrimary: Color(0xFFFFFFFF),
    textPrimary: Color(0xFF101828),
    textMuted: Color(0xFF667085),
    isDark: false,
  );

  /// DARK.
  ///
  /// Contrast on `surface` #222735:
  ///   textPrimary #ECEFF7 12.95:1 · textMuted #98A3BE 5.90:1
  ///   primary #5B9DFF 5.47:1 · success #46D69A 8.05:1 · danger #FF6B80 5.45:1
  /// All clear AA as text, so the `…OnSurface` variants are the same colours —
  /// the split exists for the light theme's benefit, and keeping the field
  /// present means call sites do not branch on brightness.
  static const dark = ClayPalette(
    // 70% of the screen is these two. #050505 for the page, #0A0A0A wherever a large
    // area needs to sit a step off it.
    base: Color(0xFF050505),
    surface: Color(0xFF151515),
    elevated: Color(0xFF1D1D1D),

    // Glass edges are LIGHT, not dark — a pane catches the light along its rim, and that
    // highlight is most of what sells the material. 10% for a resting panel, 16% for one
    // that is focused or selected.
    border: Color(0x1AFFFFFF),
    borderStrong: Color(0x29FFFFFF),

    glassFill: Color(0x0DFFFFFF),
    glassFillStrong: Color(0x14FFFFFF),
    glow: Color(0x2EFF8500),

    highlight: Color(0x14FFFFFF),
    // Near-black on near-black is invisible, so on this palette the shadow only separates
    // a floating sheet from the page. Structure comes from the light border instead.
    shadow: Color(0xB3000000),

    // The 10%. Expressway Orange, straight from the mark.
    primary: Color(0xFFFF8500),
    primarySoft: Color(0x24FF8500),
    primaryOnSurface: Color(0xFFFF8500),

    success: Color(0xFF32D583),
    successOnSurface: Color(0xFF32D583),
    warning: Color(0xFFFFB020),
    warningOnSurface: Color(0xFFFFB020),
    danger: Color(0xFFFF4D4F),
    dangerOnSurface: Color(0xFFFF4D4F),

    // Orange is bright enough that black on top of it beats white — 8.7:1 against 2.4:1.
    onPrimary: Color(0xFF0A0A0A),

    // The 20%.
    textPrimary: Color(0xFFFFFFFF),
    textMuted: Color(0xFFA3A3A3),
    isDark: true,
  );

  ClayPalette lerpTo(ClayPalette other, double t) => ClayPalette(
    base: Color.lerp(base, other.base, t)!,
    surface: Color.lerp(surface, other.surface, t)!,
    border: Color.lerp(border, other.border, t)!,
    borderStrong: Color.lerp(borderStrong, other.borderStrong, t)!,
    elevated: Color.lerp(elevated, other.elevated, t)!,
    glassFill: Color.lerp(glassFill, other.glassFill, t)!,
    glassFillStrong: Color.lerp(glassFillStrong, other.glassFillStrong, t)!,
    glow: Color.lerp(glow, other.glow, t)!,
    highlight: Color.lerp(highlight, other.highlight, t)!,
    shadow: Color.lerp(shadow, other.shadow, t)!,
    primary: Color.lerp(primary, other.primary, t)!,
    primarySoft: Color.lerp(primarySoft, other.primarySoft, t)!,
    primaryOnSurface: Color.lerp(primaryOnSurface, other.primaryOnSurface, t)!,
    success: Color.lerp(success, other.success, t)!,
    successOnSurface: Color.lerp(successOnSurface, other.successOnSurface, t)!,
    warning: Color.lerp(warning, other.warning, t)!,
    warningOnSurface: Color.lerp(warningOnSurface, other.warningOnSurface, t)!,
    danger: Color.lerp(danger, other.danger, t)!,
    dangerOnSurface: Color.lerp(dangerOnSurface, other.dangerOnSurface, t)!,
    onPrimary: Color.lerp(onPrimary, other.onPrimary, t)!,
    textPrimary: Color.lerp(textPrimary, other.textPrimary, t)!,
    textMuted: Color.lerp(textMuted, other.textMuted, t)!,
    isDark: t < 0.5 ? isDark : other.isDark,
  );
}
