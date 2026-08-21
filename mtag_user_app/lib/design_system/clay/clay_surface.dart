import 'dart:ui' show ImageFilter;

import 'package:flutter/material.dart';
import 'package:mtag_user_app/design_system/theme/clay_theme.dart';
import 'package:mtag_user_app/design_system/tokens/clay_metrics.dart';
import 'package:mtag_user_app/design_system/tokens/clay_palette.dart';

/// How a surface is rendered.
///
/// The app mixes three materials on purpose, each doing the job it is actually good at:
///
///   * **[glass]** — ~70% of surfaces. The wallet card, tag/toll status, transaction
///     cards, promos. A translucent pane over the ambient glow, rimmed with light.
///   * **[neumorphic]** — used SPARINGLY, and only on interactive controls. A whole app of
///     it turns into an unreadable field of same-coloured lumps; a single raised button in
///     a glass panel reads as the one thing you can press.
///   * **[clay]** — illustrations, empty states, onboarding, success moments. Friendly and
///     soft, which is right for "nothing here yet" and wrong for a payment screen.
///
/// [flat] and [pressed] remain for nested content and inputs.
enum ClayDepthStyle {
  /// Frosted pane: translucent fill, light rim, optional backdrop blur.
  glass,

  /// Soft extruded control. Interactive elements only.
  neumorphic,

  /// Puffy and inflated. Illustrations and empty states only.
  clay,

  /// Solid card — no translucency. For anything that must stay legible over an unknown
  /// backdrop.
  raised,

  /// Recessed: inputs, and controls while held.
  pressed,

  /// Fill only, no edge treatment. Content nested inside a surface that already has one.
  flat,
}

/// The one primitive every other surface composes from.
class ClaySurface extends StatelessWidget {
  const ClaySurface({
    this.child,
    this.depth = ClayElevation.card,
    this.radius = ClayRadius.card,
    this.color,
    this.style = ClayDepthStyle.glass,
    this.padding = EdgeInsets.zero,
    this.margin = EdgeInsets.zero,
    this.width,
    this.height,
    this.borderColor,
    this.showBorder = true,
    this.blur = true,
    this.clipChild = false,
    super.key,
  });

  final Widget? child;
  final double depth;
  final double radius;
  final Color? color;
  final ClayDepthStyle style;
  final EdgeInsets padding;
  final EdgeInsets margin;
  final double? width;
  final double? height;
  final Color? borderColor;
  final bool showBorder;

  /// Whether a [glass] surface actually runs a [BackdropFilter].
  ///
  /// **Off for anything inside a long list.** A real backdrop blur forces a save layer and
  /// re-reads the framebuffer per surface; a 200-row transaction list with one per row
  /// drops frames on exactly the budget phones this ships to. Over a flat area the blur is
  /// also invisible — there is nothing behind to smear — so a row loses nothing by
  /// rendering as a plain translucent pane. Reserve `blur: true` for the few panels that
  /// genuinely sit over the ambient glow.
  final bool blur;

  final bool clipChild;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final borderRadius = BorderRadius.circular(radius);

    Widget? content = child == null
        ? null
        : Padding(padding: padding, child: child);
    if (clipChild && content != null) {
      content = ClipRRect(borderRadius: borderRadius, child: content);
    }

    final decorated = Container(
      width: width,
      height: height,
      decoration: _decoration(palette, borderRadius),
      child: content,
    );

    Widget surface = decorated;

    if (style == ClayDepthStyle.glass && blur) {
      surface = ClipRRect(
        borderRadius: borderRadius,
        child: BackdropFilter(
          filter: ImageFilter.blur(
            sigmaX: ClayBlur.pane,
            sigmaY: ClayBlur.pane,
          ),
          child: decorated,
        ),
      );
    }

    return margin == EdgeInsets.zero
        ? surface
        : Padding(padding: margin, child: surface);
  }

  BoxDecoration _decoration(ClayPalette palette, BorderRadius borderRadius) {
    switch (style) {
      case ClayDepthStyle.glass:
        return BoxDecoration(
          borderRadius: borderRadius,
          // A gentle top-to-bottom fade, not a flat wash: light falls on the top edge of a
          // real pane and drains away down it. This is the cheapest cue that sells glass,
          // and unlike the blur it costs nothing.
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              color ?? palette.glassFillStrong,
              color ?? palette.glassFill,
            ],
          ),
          border: showBorder
              ? Border.all(
                  color: borderColor ?? palette.border,
                )
              : null,
          boxShadow: depth > 0
              ? [
                  BoxShadow(
                    color: palette.shadow,
                    offset: Offset(0, depth),
                    blurRadius: depth * 3,
                  ),
                ]
              : null,
        );

      case ClayDepthStyle.neumorphic:
        // Two shadows, light up-left and dark down-right. On a near-black ground the
        // "light" one is a low-alpha white rather than a real colour — anything stronger
        // stops reading as a lit edge and starts reading as a glowing outline.
        return BoxDecoration(
          color: color ?? palette.elevated,
          borderRadius: borderRadius,
          boxShadow: [
            BoxShadow(
              color: palette.shadow,
              offset: Offset(depth, depth),
              blurRadius: depth * 2.5,
            ),
            BoxShadow(
              color: palette.highlight,
              offset: Offset(-depth * 0.6, -depth * 0.6),
              blurRadius: depth * 2,
            ),
          ],
        );

      case ClayDepthStyle.clay:
        // Puffier and rounder than neumorphic, and unapologetically soft. Only ever used
        // where the content is an illustration or an empty state.
        return BoxDecoration(
          color: color ?? palette.elevated,
          borderRadius: borderRadius,
          boxShadow: [
            BoxShadow(
              color: palette.shadow,
              offset: Offset(depth * 0.8, depth * 1.4),
              blurRadius: depth * 3.5,
            ),
            BoxShadow(
              color: palette.highlight,
              offset: Offset(-depth, -depth),
              blurRadius: depth * 3,
            ),
          ],
        );

      case ClayDepthStyle.raised:
        return BoxDecoration(
          color: color ?? palette.surface,
          borderRadius: borderRadius,
          border: showBorder
              ? Border.all(
                  color: borderColor ?? palette.border,
                )
              : null,
          boxShadow: depth > 0
              ? [
                  BoxShadow(
                    color: palette.shadow,
                    offset: Offset(0, depth),
                    blurRadius: depth * 3,
                  ),
                ]
              : null,
        );

      case ClayDepthStyle.pressed:
        // Darker than the surface it sits in, so an input reads as an opening cut into the
        // panel rather than another panel stacked on it.
        return BoxDecoration(
          color: color ?? palette.base,
          borderRadius: borderRadius,
          border: showBorder
              ? Border.all(
                  color: borderColor ?? palette.border,
                )
              : null,
        );

      case ClayDepthStyle.flat:
        return BoxDecoration(
          color: color ?? palette.surface,
          borderRadius: borderRadius,
        );
    }
  }
}
