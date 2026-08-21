import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:mtag_user_app/design_system/theme/clay_theme.dart';

/// A ring gauge carved into the clay, with the filled arc raised out of it.
///
/// Used for "how much of the Rs. 50 entry minimum do you have" and similar
/// bounded values. The track is an inset groove and the value is a rounded bar
/// sitting in it, which is the same material story as every other surface.
///
/// [value] is clamped to 0..1; a balance well over the target still reads as a
/// full ring rather than overflowing.
class ClayProgressRing extends StatelessWidget {
  const ClayProgressRing({
    required this.value,
    this.size = 72,
    this.thickness = 9,
    this.color,
    this.child,
    this.semanticLabel,
    super.key,
  });

  final double value;
  final double size;
  final double thickness;
  final Color? color;
  final Widget? child;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    return Semantics(
      label: semanticLabel,
      value: '${(value.clamp(0.0, 1.0) * 100).round()}%',
      child: SizedBox(
        width: size,
        height: size,
        child: CustomPaint(
          painter: _RingPainter(
            value: value.clamp(0.0, 1.0),
            thickness: thickness,
            track: palette.shadow,
            trackHighlight: palette.highlight,
            fill: color ?? palette.primary,
          ),
          child: child == null ? null : Center(child: child),
        ),
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  const _RingPainter({
    required this.value,
    required this.thickness,
    required this.track,
    required this.trackHighlight,
    required this.fill,
  });

  final double value;
  final double thickness;
  final Color track;
  final Color trackHighlight;
  final Color fill;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    final radius = (size.shortestSide - thickness) / 2;
    final center = rect.center;
    final arcRect = Rect.fromCircle(center: center, radius: radius);

    // Groove: a dark arc offset up-left and a light one down-right, the same
    // inset logic as ClaySurface's pressed style, applied to a circle.
    void groove(Offset offset, Color color) {
      canvas.drawArc(
        arcRect.shift(offset),
        0,
        math.pi * 2,
        false,
        Paint()
          ..color = color
          ..style = PaintingStyle.stroke
          ..strokeWidth = thickness
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 2),
      );
    }

    groove(const Offset(-1.2, -1.2), track);
    groove(const Offset(1.2, 1.2), trackHighlight);

    if (value <= 0) return;

    canvas.drawArc(
      arcRect,
      // Start at 12 o'clock and go clockwise, which is how a gauge is read.
      -math.pi / 2,
      math.pi * 2 * value,
      false,
      Paint()
        ..color = fill
        ..style = PaintingStyle.stroke
        ..strokeWidth = thickness
        ..strokeCap = StrokeCap.round,
    );
  }

  @override
  bool shouldRepaint(_RingPainter old) =>
      old.value != value ||
      old.thickness != thickness ||
      old.fill != fill ||
      old.track != track;
}
