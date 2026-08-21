import 'package:flutter/material.dart';
import 'package:mtag_user_app/design_system/theme/clay_theme.dart';

/// The ambient light behind the glass.
///
/// **Glassmorphism does not work on a flat field.** A backdrop blur over a uniform
/// #050505 background blurs nothing: it costs a full-screen save layer and produces a
/// result pixel-identical to a plain translucent fill. Frosted glass only reads as glass
/// when there is something behind it to smear — so this puts something there.
///
/// Two soft orange pools, well off-centre and heavily feathered, sitting under the page
/// content. They are the reason a panel's edge catches light and its middle glows faintly
/// warm. Their alpha is low by design: at the specified 70/20/10 split, orange is an
/// accent, and an ambient wash bright enough to notice on its own has already blown the
/// budget.
///
/// Cheap: two `RadialGradient`s in one `DecoratedBox`, painted once, no blur filter.
class ClayAmbient extends StatelessWidget {
  const ClayAmbient({required this.child, this.intensity = 1.0, super.key});

  final Widget child;

  /// Scales both pools. Raised a little on the dashboard, where the wallet card is the
  /// subject; dropped on dense screens, where a glow behind a list is just noise.
  final double intensity;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final glow = palette.glow.withValues(
      alpha: (palette.glow.a * intensity).clamp(0.0, 1.0),
    );

    return Stack(
      // EXPAND, and it is load-bearing rather than cosmetic.
      //
      // A Scaffold hands `body` LOOSE horizontal constraints and pins the result to the
      // left edge. A bare Stack sizes to its non-positioned child, so a page whose widest
      // child is a fixed-width box (a logo, a 320px glow) collapsed to that width and sat
      // against the left edge of the screen — invisible on a phone narrower than the
      // content, glaring on a tablet, a foldable, or any phone in landscape.
      //
      // Expanding also makes the `Positioned.fill` glow below mean what it says: the pools
      // are positioned against the PAGE, and a Stack that had shrunk to its child was
      // painting them against the child instead.
      //
      // Requires bounded constraints in both axes, which every use site satisfies by being
      // a Scaffold `body`. Nesting one inside a scroll view now throws instead of silently
      // mislaying the page — the louder failure of the two.
      fit: StackFit.expand,
      children: [
        Positioned.fill(
          child: DecoratedBox(
            decoration: BoxDecoration(color: palette.base),
            child: Stack(
              children: [
                // Upper pool — sits behind the hero/wallet card.
                Positioned(
                  top: -180,
                  left: -120,
                  right: -40,
                  height: 520,
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      gradient: RadialGradient(
                        colors: [glow, Colors.transparent],
                        radius: 0.75,
                      ),
                    ),
                  ),
                ),
                // Lower pool — keeps the bottom of a long screen from going dead flat.
                Positioned(
                  bottom: -220,
                  right: -160,
                  width: 460,
                  height: 460,
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      gradient: RadialGradient(
                        colors: [
                          glow.withValues(alpha: glow.a * 0.6),
                          Colors.transparent,
                        ],
                        radius: 0.7,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        child,
      ],
    );
  }
}
