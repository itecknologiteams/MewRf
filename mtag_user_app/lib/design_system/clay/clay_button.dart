import 'package:flutter/material.dart';
import 'package:mtag_user_app/design_system/clay/clay_surface.dart';
import 'package:mtag_user_app/design_system/theme/clay_theme.dart';
import 'package:mtag_user_app/design_system/tokens/clay_metrics.dart';
import 'package:mtag_user_app/design_system/tokens/clay_palette.dart';

enum ClayButtonVariant {
  /// Filled with the primary colour. One per screen — the thing you came to do.
  primary,

  /// Clay-coloured, same depth. The everyday button.
  tonal,

  /// No surface at all until pressed. Cancel, "not now", tertiary links.
  ghost,

  /// Filled with the danger colour. Destructive, and rare in a read-mostly app.
  danger,
}

/// The signature interaction of the whole app: a surface that dips under the
/// finger, raised -> pressed over 120ms.
///
/// Everything about this widget exists to make that dip feel physical:
/// the surface swap is crossfaded rather than switched, the label scales down a
/// hair so the whole button feels compressed rather than merely re-shaded, and
/// the tap is dispatched on release so a drag-off cancels — which is what a real
/// button does.
class ClayButton extends StatefulWidget {
  const ClayButton({
    required this.label,
    required this.onPressed,
    this.variant = ClayButtonVariant.tonal,
    this.icon,
    this.expand = false,
    this.loading = false,
    this.depth = ClayDepth.control,
    this.radius = ClayRadius.control,
    this.padding = const EdgeInsets.symmetric(
      horizontal: ClaySpace.xl,
      vertical: ClaySpace.lg,
    ),
    super.key,
  });

  final String label;

  /// Null disables the button. Also true while [loading].
  final VoidCallback? onPressed;

  final ClayButtonVariant variant;
  final IconData? icon;

  /// Fill the available width.
  final bool expand;

  /// Shows a spinner in place of the icon and blocks input. Used on money
  /// operations, where a double tap must not become two POSTs.
  final bool loading;

  final double depth;
  final double radius;
  final EdgeInsets padding;

  @override
  State<ClayButton> createState() => _ClayButtonState();
}

class _ClayButtonState extends State<ClayButton> {
  bool _down = false;

  bool get _enabled => widget.onPressed != null && !widget.loading;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final duration = clayPressDuration(context);

    // fill / content / border, per variant.
    //
    // `tonal` is the NEUMORPHIC one, and buttons are the only place this design uses
    // neumorphism at all. A single extruded control inside a glass panel reads
    // unmistakably as "the thing you press"; a screen full of them reads as a field of
    // same-coloured lumps with the text fighting the texture.
    //
    // primary and danger stay solid fills — the main action of a payment screen should be
    // the least subtle thing on it.
    final (
      Color? fill,
      Color content,
      Color? border,
    ) = switch (widget.variant) {
      ClayButtonVariant.primary => (palette.primary, palette.onPrimary, null),
      ClayButtonVariant.danger => (palette.danger, palette.onPrimary, null),
      ClayButtonVariant.tonal => (
        palette.elevated,
        palette.textPrimary,
        palette.border,
      ),
      ClayButtonVariant.ghost => (null, palette.primaryOnSurface, null),
    };
    final isNeumorphic = widget.variant == ClayButtonVariant.tonal;

    // Disabled keeps the shape and fades the content. Removing the surface would make a
    // disabled primary button look like empty page, and people stop looking for it.
    final contentColor = _enabled ? content : content.withValues(alpha: 0.4);
    final fillColor = fill == null
        ? null
        : (_enabled
              ? (_down ? _pressedFill(fill, palette) : fill)
              : Color.alphaBlend(
                  palette.base.withValues(alpha: 0.6),
                  fill,
                ));

    final label = Row(
      mainAxisSize: widget.expand ? MainAxisSize.max : MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (widget.loading)
          SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(
              strokeWidth: 2.2,
              valueColor: AlwaysStoppedAnimation(contentColor),
            ),
          )
        else if (widget.icon != null)
          Icon(widget.icon, size: 20, color: contentColor),
        if (widget.loading || widget.icon != null)
          const SizedBox(width: ClaySpace.md),
        Flexible(
          child: Text(
            widget.label,
            textAlign: TextAlign.center,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(
              context,
            ).textTheme.labelLarge!.copyWith(color: contentColor),
          ),
        ),
      ],
    );

    final surface = AnimatedContainer(
      duration: duration,
      curve: ClayMotion.ease,
      padding: widget.padding,
      decoration: BoxDecoration(
        color: fillColor,
        borderRadius: BorderRadius.circular(widget.radius),
        border: border == null
            ? null
            : Border.all(
                color: _down ? palette.borderStrong : border,
              ),
        boxShadow: !_enabled || widget.depth <= 0
            ? null
            : isNeumorphic && !_down
            // The extruded pair: dark down-right, a faint light up-left. Both collapse
            // while held, so the control visibly sinks under the finger.
            ? [
                BoxShadow(
                  color: palette.shadow,
                  offset: Offset(widget.depth, widget.depth),
                  blurRadius: widget.depth * 2.5,
                ),
                BoxShadow(
                  color: palette.highlight,
                  offset: Offset(-widget.depth * 0.6, -widget.depth * 0.6),
                  blurRadius: widget.depth * 2,
                ),
              ]
            : fill != null
            ? [
                BoxShadow(
                  color: palette.shadow,
                  offset: Offset(0, widget.depth),
                  blurRadius: widget.depth * 3,
                ),
              ]
            : null,
      ),
      child: label,
    );

    final button = Semantics(
      button: true,
      enabled: _enabled,
      label: widget.label,
      child: GestureDetector(
        onTapDown: _enabled ? (_) => setState(() => _down = true) : null,
        onTapUp: _enabled ? (_) => setState(() => _down = false) : null,
        onTapCancel: _enabled ? () => setState(() => _down = false) : null,
        onTap: _enabled ? widget.onPressed : null,
        behavior: HitTestBehavior.opaque,
        child: AnimatedScale(
          scale: _down && _enabled ? 0.97 : 1,
          duration: duration,
          curve: ClayMotion.ease,
          child: surface,
        ),
      ),
    );

    return widget.expand
        ? SizedBox(width: double.infinity, child: button)
        : button;
  }

  /// A filled button darkens while held, which is the clearest possible "yes, that one".
  Color _pressedFill(Color fill, ClayPalette palette) =>
      Color.alphaBlend(Colors.black.withValues(alpha: 0.12), fill);
}

/// A round icon button. Same press language, no label.
class ClayIconButton extends StatefulWidget {
  const ClayIconButton({
    required this.icon,
    required this.onPressed,
    required this.semanticLabel,
    this.size = 44,
    this.iconSize = 20,
    this.color,
    this.depth = ClayDepth.control,
    super.key,
  });

  final IconData icon;
  final VoidCallback? onPressed;

  /// Required: an icon-only control with no label is invisible to a screen
  /// reader, and this app's users include people who cannot see the icon.
  final String semanticLabel;

  final double size;
  final double iconSize;
  final Color? color;
  final double depth;

  @override
  State<ClayIconButton> createState() => _ClayIconButtonState();
}

class _ClayIconButtonState extends State<ClayIconButton> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final enabled = widget.onPressed != null;
    final tint = (widget.color ?? palette.textPrimary).withValues(
      alpha: enabled ? 1.0 : 0.4,
    );

    return Semantics(
      button: true,
      enabled: enabled,
      label: widget.semanticLabel,
      child: GestureDetector(
        onTapDown: enabled ? (_) => setState(() => _down = true) : null,
        onTapUp: enabled ? (_) => setState(() => _down = false) : null,
        onTapCancel: enabled ? () => setState(() => _down = false) : null,
        onTap: widget.onPressed,
        behavior: HitTestBehavior.opaque,
        child: AnimatedScale(
          scale: _down && enabled ? 0.92 : 1,
          duration: clayPressDuration(context),
          curve: ClayMotion.ease,
          child: ClaySurface(
            depth: widget.depth,
            radius: ClayRadius.pill,
            borderColor: _down ? palette.borderStrong : null,
            child: SizedBox(
              width: widget.size,
              height: widget.size,
              child: Center(
                child: Icon(widget.icon, size: widget.iconSize, color: tint),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
