import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:mtag_user_app/design_system/clay.dart';

/// The phase of the OTP ceremony. Drives both layout and colour.
enum OtpPhase { entering, verifying, success, error }

/// Four digit boxes that animate between three layouts.
///
/// The layouts are a ROW (entering), a 2x2 GRID (as verification begins), and a single
/// CONVERGED point at the centre (verified). Each box's position is interpolated between
/// those targets rather than being re-parented, which is what makes them appear to travel —
/// the Flutter equivalent of Framer Motion's shared-layout animation.
///
/// Interpolating explicitly, rather than letting a Wrap reflow, is deliberate: a reflow
/// moves children instantly to their new slots, so the boxes would JUMP from one row to two.
/// The whole effect is in the travel.
///
/// ## What this widget does NOT do, and why
///
/// Scale and opacity are applied ONCE around the whole group rather than per box. They are
/// identical for every box at a given [progress], so four `Opacity` widgets meant four
/// `saveLayer` calls per frame for one visual effect — and `saveLayer` is the most expensive
/// thing a simple animation can ask for.
///
/// The boxes are plain `Container`s, not `AnimatedContainer`s. An implicit animation is
/// pointless while an explicit one already drives every frame: it added four more tickers
/// and four more `BoxDecoration` allocations per frame to interpolate values that were
/// already being handed to it. The border colour is lerped directly instead, which is both
/// cheaper and actually in step with the layout, where the implicit version lagged it.
class OtpBoxes extends StatelessWidget {
  const OtpBoxes({
    required this.code,
    required this.phase,
    required this.progress,
    this.length = 4,
    super.key,
  });

  /// Digits entered so far, shortest-first. May be shorter than [length].
  final String code;

  final OtpPhase phase;

  /// 0 = row, 1 = fully converged. Drives the layout transition.
  final double progress;

  final int length;

  static const _box = Size(58, 62);
  static const _gap = 14.0;

  /// Where box [index] sits for a given transition [t].
  ///
  /// t 0.0 → 0.5 : row  → 2x2 grid
  /// t 0.5 → 1.0 : grid → converged at the centre
  Offset _offsetFor(int index, double t) {
    final rowWidth = length * _box.width + (length - 1) * _gap;
    final row = Offset(
      -rowWidth / 2 + index * (_box.width + _gap) + _box.width / 2,
      0,
    );

    final col = index % 2;
    final line = index ~/ 2;
    final grid = Offset(
      (col - 0.5) * (_box.width + _gap),
      (line - 0.5) * (_box.height + _gap),
    );

    if (t <= 0.5) {
      return Offset.lerp(row, grid, Curves.easeOutCubic.transform(t / 0.5))!;
    }
    return Offset.lerp(
      grid,
      Offset.zero,
      Curves.easeInCubic.transform((t - 0.5) / 0.5),
    )!;
  }

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final t = progress.clamp(0.0, 1.0);

    // Both are the same for every box, so they are applied to the GROUP. Per box this was
    // four saveLayers and four Transform layers a frame for one effect.
    final groupScale = 1 - 0.35 * math.max(0.0, (t - 0.5) / 0.5);
    final groupOpacity = 1 - 0.85 * math.max(0.0, (t - 0.6) / 0.4);

    Widget group = Stack(
      alignment: Alignment.center,
      clipBehavior: Clip.none,
      children: [
        for (var i = 0; i < length; i++)
          Transform.translate(
            offset: _offsetFor(i, t),
            child: _Box(
              digit: i < code.length ? code[i] : null,
              // The box awaiting input carries the accent, a cursor and a glow.
              isActive: phase == OtpPhase.entering && i == code.length,
              phase: phase,
              palette: palette,
            ),
          ),
      ],
    );

    if (groupScale != 1) {
      group = Transform.scale(scale: groupScale, child: group);
    }
    // Guarded: `Opacity` skips its saveLayer entirely at exactly 1.0, and the boxes sit at
    // full opacity for the whole entry phase — which is where the user actually spends time.
    if (groupOpacity < 1) {
      group = Opacity(opacity: groupOpacity, child: group);
    }

    return SizedBox(height: _box.height * 2 + _gap + 8, child: group);
  }
}

class _Box extends StatelessWidget {
  const _Box({
    required this.digit,
    required this.isActive,
    required this.phase,
    required this.palette,
  });

  final String? digit;
  final bool isActive;
  final OtpPhase phase;
  final ClayPalette palette;

  @override
  Widget build(BuildContext context) {
    final border = switch (phase) {
      OtpPhase.error => palette.danger,
      OtpPhase.success => palette.success,
      _ when isActive => palette.primary,
      _ => palette.border,
    };

    return Container(
      width: OtpBoxes._box.width,
      height: OtpBoxes._box.height,
      decoration: BoxDecoration(
        color: palette.glassFill,
        borderRadius: BorderRadius.circular(ClayRadius.control),
        border: Border.all(color: border, width: isActive ? 1.6 : 1),
        boxShadow: isActive
            ? [
                // The glow under the active box, straight from the reference.
                BoxShadow(
                  color: palette.primary.withValues(alpha: 0.30),
                  offset: const Offset(0, 4),
                  blurRadius: 14,
                ),
              ]
            : null,
      ),
      alignment: Alignment.center,
      child: digit != null
          ? Text(
              digit!,
              style: Theme.of(context).textTheme.displaySmall,
              textDirection: TextDirection.ltr,
            )
          : isActive
          ? const _Caret()
          : null,
    );
  }
}

/// The blinking caret in the active box.
class _Caret extends StatefulWidget {
  const _Caret();

  @override
  State<_Caret> createState() => _CaretState();
}

class _CaretState extends State<_Caret> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 620),
  );

  @override
  void initState() {
    super.initState();
    _c.repeat(reverse: true);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // A caret that blinks forever is exactly what reduce-motion is for.
    if (clayReduceMotion(context) && _c.isAnimating) {
      _c
        ..stop()
        ..value = 1;
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    return FadeTransition(
      opacity: _c,
      child: Container(width: 2, height: 26, color: palette.textPrimary),
    );
  }
}
