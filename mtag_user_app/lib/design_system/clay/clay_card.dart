import 'package:flutter/material.dart';
import 'package:mtag_user_app/design_system/clay/clay_button.dart'
    show ClayButton;
import 'package:mtag_user_app/design_system/clay/clay_motion.dart';
import 'package:mtag_user_app/design_system/clay/clay_surface.dart';
import 'package:mtag_user_app/design_system/theme/clay_theme.dart';
import 'package:mtag_user_app/design_system/tokens/clay_metrics.dart';

/// A glass card. The workhorse container behind the wallet, tag status and transaction
/// surfaces — roughly 70% of what is on screen.
///
/// `blur` is OFF by default and switched on only for the few panels that genuinely sit
/// over the ambient glow. See ClaySurface.blur: a real backdrop filter in a list builder
/// drops frames, and over a flat area it is invisible anyway.
///
/// When [onTap] is given it scales down a hair and darkens its border while held — the
/// same gesture language as [ClayButton], so a tappable card advertises itself by
/// responding rather than by growing an affordance.
class ClayCard extends StatefulWidget {
  const ClayCard({
    required this.child,
    this.onTap,
    this.depth = ClayDepth.card,
    this.radius = ClayRadius.card,
    this.padding = const EdgeInsets.all(ClaySpace.cardPadding),
    this.margin = EdgeInsets.zero,
    this.color,
    this.width,
    this.semanticLabel,
    super.key,
    this.style = ClayDepthStyle.glass,
    this.blur = false,
  });

  final Widget child;
  final VoidCallback? onTap;
  final double depth;
  final double radius;
  final EdgeInsets padding;

  /// Defaults to glass. Set to [ClayDepthStyle.clay] for an illustration or empty state,
  /// or [ClayDepthStyle.raised] where the card must stay legible over unknown content.
  final ClayDepthStyle style;

  /// Run a real backdrop blur. Only for panels over the ambient glow — never in a list.
  final bool blur;
  final EdgeInsets margin;
  final Color? color;
  final double? width;
  final String? semanticLabel;

  @override
  State<ClayCard> createState() => _ClayCardState();
}

class _ClayCardState extends State<ClayCard> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;

    // Pressed feedback is a scale plus a darker border, not a swap to a recessed surface.
    // With a bordered system there is no depth to invert — and darkening the hairline is
    // the most direct way to say "this specific edge is the thing you are touching".
    final surface = AnimatedContainer(
      duration: clayPressDuration(context),
      curve: ClayMotion.ease,
      margin: widget.margin,
      width: widget.width,
      child: ClaySurface(
        depth: widget.depth,
        radius: widget.radius,
        color: widget.color,
        style: widget.style,
        blur: widget.blur,
        padding: widget.padding,
        borderColor: _down ? palette.borderStrong : null,
        child: widget.child,
      ),
    );

    if (widget.onTap == null) return surface;

    return ClayPressable(
      onTap: widget.onTap,
      semanticLabel: widget.semanticLabel,
      child: Listener(
        // Listener rather than another GestureDetector: ClayPressable already owns the tap
        // gesture, and a second recogniser competing for it would make the card need two
        // taps in a scrollable.
        onPointerDown: (_) => setState(() => _down = true),
        onPointerUp: (_) => setState(() => _down = false),
        onPointerCancel: (_) => setState(() => _down = false),
        child: surface,
      ),
    );
  }
}
