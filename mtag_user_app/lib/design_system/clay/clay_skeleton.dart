import 'package:flutter/material.dart';
import 'package:mtag_user_app/design_system/clay/clay_surface.dart';
import 'package:mtag_user_app/design_system/theme/clay_theme.dart';
import 'package:mtag_user_app/design_system/tokens/clay_metrics.dart';

/// A shimmering placeholder block.
///
/// Full-page loads never get a spinner in this app. A spinner says "wait" and
/// nothing else; a skeleton in the shape of the content says what is coming and
/// how much of it, so the page does not jump when data lands. It is also the
/// difference between an app that feels slow and one that feels busy.
///
/// The shimmer is dropped under reduce-motion — the flat block remains, so the
/// loading state is still legible without the sweep.
class ClaySkeleton extends StatefulWidget {
  const ClaySkeleton({
    this.width,
    this.height = 16,
    this.radius = ClayRadius.control,
    this.margin = EdgeInsets.zero,
    super.key,
  });

  /// A text-line-shaped skeleton.
  const ClaySkeleton.line({
    double? width,
    double height = 14,
    EdgeInsets margin = EdgeInsets.zero,
    Key? key,
  }) : this(
         width: width,
         height: height,
         radius: ClayRadius.pill,
         margin: margin,
         key: key,
       );

  final double? width;
  final double height;
  final double radius;
  final EdgeInsets margin;

  @override
  State<ClaySkeleton> createState() => _ClaySkeletonState();
}

class _ClaySkeletonState extends State<ClaySkeleton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: ClayMotion.shimmer,
  );

  @override
  void initState() {
    super.initState();
    // Started in didChangeDependencies-equivalent below; MediaQuery is not
    // readable from initState.
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (clayReduceMotion(context)) {
      _controller.stop();
    } else if (!_controller.isAnimating) {
      _controller.repeat();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final reduceMotion = clayReduceMotion(context);

    // Flat, not raised: a skeleton is content-shaped, and content nested in an
    // already-raised card must not stack another shadow pair.
    final block = ClaySurface(
      style: ClayDepthStyle.flat,
      radius: widget.radius,
      width: widget.width,
      height: widget.height,
      margin: widget.margin,
      color: Color.alphaBlend(
        palette.textMuted.withValues(alpha: palette.isDark ? 0.16 : 0.13),
        palette.surface,
      ),
    );

    if (reduceMotion) return ExcludeSemantics(child: block);

    return ExcludeSemantics(
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          // -1 -> 2 so the highlight enters off-screen-left and leaves
          // off-screen-right, rather than materialising inside the block.
          final t = -1.0 + 3.0 * _controller.value;
          return ShaderMask(
            blendMode: BlendMode.srcATop,
            shaderCallback: (bounds) => LinearGradient(
              begin: Alignment(t - 0.35, 0),
              end: Alignment(t + 0.35, 0),
              colors: [
                Colors.transparent,
                palette.highlight.withValues(
                  alpha: palette.isDark ? 0.30 : 0.55,
                ),
                Colors.transparent,
              ],
            ).createShader(bounds),
            child: block,
          );
        },
      ),
    );
  }
}

/// A card-shaped skeleton: raised surface, flat blocks inside.
class ClaySkeletonCard extends StatelessWidget {
  const ClaySkeletonCard({
    this.lines = 3,
    this.height,
    this.depth = ClayDepth.card,
    super.key,
  });

  final int lines;
  final double? height;
  final double depth;

  @override
  Widget build(BuildContext context) {
    return ClaySurface(
      depth: depth,
      height: height,
      padding: const EdgeInsets.all(ClaySpace.cardPadding),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          for (var i = 0; i < lines; i++)
            ClaySkeleton.line(
              width: i == 0 ? 140 : (i.isEven ? 200 : 110),
              height: i == 0 ? 20 : 13,
              margin: EdgeInsets.only(
                bottom: i == lines - 1 ? 0 : ClaySpace.md,
              ),
            ),
        ],
      ),
    );
  }
}
