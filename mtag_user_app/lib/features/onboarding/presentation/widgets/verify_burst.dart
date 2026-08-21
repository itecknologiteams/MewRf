import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:mtag_user_app/design_system/clay.dart';

/// The green particle burst that plays over verification.
///
/// Two concentric rounded-square rings expand outward while diamond particles fly along
/// their radii, matching the reference. Drawn in a single [CustomPainter] rather than as
/// dozens of widgets: this runs for well under a second on a phone that is also doing a
/// network round trip, and forty animated widgets would each need their own element,
/// RenderObject and layout pass for no visual gain.
///
/// Particle angles and radii come from a SEEDED Random, so the burst looks scattered but is
/// identical every run — which also makes it stable in a golden test.
///
/// The scatter is computed ONCE into [_Particle.table] rather than per paint. Reseeding
/// `Random(42)` and running 26 sin/cos pairs on every frame produced the same numbers every
/// time — a fixed table by definition, recomputed 120 times a second. The `Paint` objects are
/// reused for the same reason: the old version allocated 28 of them per frame, which is 3,400
/// short-lived objects over one 1.1s burst, all of it garbage for the collector to sweep
/// during the animation.
class VerifyBurst extends StatelessWidget {
  const VerifyBurst({
    required this.progress,
    this.particles = 26,
    super.key,
  });

  /// 0 → 1 across the burst.
  final double progress;

  final int particles;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    return IgnorePointer(
      child: CustomPaint(
        painter: _BurstPainter(
          progress: progress.clamp(0.0, 1.0),
          colour: palette.success,
          count: particles,
        ),
        size: Size.infinite,
      ),
    );
  }
}

class _BurstPainter extends CustomPainter {
  _BurstPainter({
    required this.progress,
    required this.colour,
    required this.count,
  });

  final double progress;
  final Color colour;
  final int count;

  /// Reused across frames. Mutating `color` on an existing Paint is free; allocating a new
  /// one per particle per frame is not.
  final _ringPaint = Paint()
    ..style = PaintingStyle.stroke
    ..strokeWidth = 1.6;
  final _particlePaint = Paint();

  @override
  void paint(Canvas canvas, Size size) {
    if (progress <= 0 || size.isEmpty) return;

    final centre = size.center(Offset.zero);
    final maxRadius = size.shortestSide * 0.46;
    final eased = Curves.easeOutCubic.transform(progress);

    // ── The two expanding rounded-square rings ──────────────────────────────
    for (final (index, delay) in const [(0, 0.0), (1, 0.18)]) {
      final local = ((progress - delay) / (1 - delay)).clamp(0.0, 1.0);
      if (local <= 0) continue;
      final r =
          maxRadius * (0.30 + 0.70 * Curves.easeOutCubic.transform(local));
      // Fades as it grows, so the ring reads as dissipating rather than stopping.
      final alpha = (1 - local) * (index == 0 ? 0.55 : 0.35);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromCenter(center: centre, width: r * 2, height: r * 2),
          Radius.circular(r * 0.42),
        ),
        _ringPaint..color = colour.withValues(alpha: alpha),
      );
    }

    // ── Diamond particles ───────────────────────────────────────────────────
    // Hold, then fade over the back half — particles should not wink out at full size.
    final alpha = (1 - math.max(0.0, (progress - 0.45) / 0.55)).clamp(0.0, 1.0);
    if (alpha <= 0) return;
    _particlePaint.color = colour.withValues(alpha: alpha * 0.85);

    final particles = _Particle.table(count);
    for (final particle in particles) {
      final distance = maxRadius * particle.spread * eased;

      canvas
        ..save()
        // The unit direction is precomputed, so no trig runs here.
        ..translate(
          centre.dx + particle.direction.dx * distance,
          centre.dy + particle.direction.dy * distance,
        )
        // A rotated square is the diamond in the reference.
        ..rotate(particle.rotation)
        ..drawRect(
          Rect.fromCenter(
            center: Offset.zero,
            width: particle.side,
            height: particle.side,
          ),
          _particlePaint,
        )
        ..restore();
    }
  }

  @override
  bool shouldRepaint(_BurstPainter old) =>
      old.progress != progress || old.colour != colour || old.count != count;
}

/// One diamond's fixed geometry.
///
/// Built once per particle count and cached. Everything here is a function of the seed
/// alone, so recomputing it per frame produced identical numbers at real cost.
class _Particle {
  const _Particle({
    required this.direction,
    required this.spread,
    required this.side,
    required this.rotation,
  });

  /// A unit vector, so paint() does no trigonometry.
  final Offset direction;
  final double spread;
  final double side;
  final double rotation;

  static final Map<int, List<_Particle>> _cache = {};

  static List<_Particle> table(int count) =>
      _cache.putIfAbsent(count, () => _build(count));

  static List<_Particle> _build(int count) {
    // The same seed the original used, so the scatter is visually unchanged.
    final random = math.Random(42);
    return List<_Particle>.unmodifiable([
      for (var i = 0; i < count; i++)
        () {
          final angle = random.nextDouble() * math.pi * 2;
          return _Particle(
            direction: Offset(math.cos(angle), math.sin(angle)),
            spread: 0.45 + random.nextDouble() * 0.55,
            side: 3.0 + random.nextDouble() * 6.0,
            rotation: math.pi / 4 + angle,
          );
        }(),
    ]);
  }
}
