import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/auth/presentation/session_controller.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// The splash and session gate.
///
/// Probes `GET /auth/me/`; the router redirects on the result. Two things it deliberately
/// does not do:
///
///   * **No spinner.** A mark that draws itself, then a quiet progress line. A spinner on a
///     cold start is the app admitting it has nothing to say.
///   * **It does not sign anyone out on a network failure.** The session is good for 7
///     days; a user opening the app in a basement gets a Retry, not a login screen. That
///     distinction is why this screen owns the error state rather than letting the router
///     fall through to login.
///
/// The animation is timed to the work, not to a fixed delay: the mark's reveal takes about
/// as long as a `/auth/me/` round trip, so on a fast connection the user sees one
/// continuous motion into the dashboard rather than an animation that finishes and then
/// waits. Nothing here BLOCKS on the animation — if the probe resolves first, the router
/// moves on immediately.
///
/// ## Sizing
///
/// Every dimension is derived from the viewport instead of hard-coded. The previous version
/// was built from fixed pixel sizes — a 320px glow and a 230px mark — which had two
/// consequences worth remembering:
///
///   1. The page collapsed to the width of its widest fixed child and, because a Scaffold
///      gives `body` loose constraints, pinned itself to the LEFT edge. Correct-looking on
///      a 360dp phone, badly off-centre on anything wider.
///   2. Nothing shrank. In landscape (a ~410dp-tall viewport) a 230px mark plus the
///      wordmark, tagline and progress line left no room, and at a large system font
///      scale it had nowhere to go.
///
/// So the mark is a fraction of the SHORTER dimension, the content column is capped so it
/// does not sprawl across a tablet, and both states are laid out so they cannot overflow.
class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen>
    with SingleTickerProviderStateMixin {
  /// Widest the content column is allowed to get.
  ///
  /// A splash stretched across a 1280dp tablet reads as a website, not an app. Capping and
  /// centring is what makes one layout serve a phone and a tablet.
  static const double _maxContentWidth = 420;

  /// The mark is bounded by BOTH axes independently, then clamped.
  ///
  /// A single fraction of the shorter side cannot serve both orientations. Tuned to the
  /// shorter side it shrank the mark on ordinary portrait phones — the one form factor that
  /// was already right — and tuned to the longer side it overflowed a landscape viewport.
  /// So width and height each impose a ceiling and the smaller wins:
  ///
  ///   * portrait phone (366x816) -> min(227, 277) = 227, i.e. the 230 it was tuned at
  ///   * tablet (800x1280)        -> clamped to 230, centred rather than sprawling
  ///   * landscape (915x412)      -> min(567, 140) = 140, which is what fits
  ///
  /// The upper clamp is the size the mark was designed at, so no viewport ever renders it
  /// larger than intended and phones are pixel-identical to before.
  static const double _markWidthFraction = 0.62;
  static const double _markHeightFraction = 0.34;
  static const double _markMin = 104;
  static const double _markMax = 230;

  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  );

  late final Animation<double> _markScale = CurvedAnimation(
    parent: _controller,
    // A touch of overshoot on the mark only. It is the one place in the app where a little
    // life is worth 100ms, because nothing is waiting behind it.
    curve: const Interval(0, 0.6, curve: Curves.easeOutBack),
  );

  late final Animation<double> _markFade = CurvedAnimation(
    parent: _controller,
    curve: const Interval(0, 0.45, curve: Curves.easeOut),
  );

  late final Animation<double> _textFade = CurvedAnimation(
    parent: _controller,
    curve: const Interval(0.35, 0.8, curve: Curves.easeOut),
  );

  late final Animation<double> _progressFade = CurvedAnimation(
    parent: _controller,
    curve: const Interval(0.6, 1, curve: Curves.easeOut),
  );

  @override
  void initState() {
    super.initState();
    _controller.forward();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (clayReduceMotion(context)) _controller.value = 1;
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final session = ref.watch(sessionControllerProvider);
    final hasError = session.hasError;

    return Scaffold(
      backgroundColor: palette.base,
      // ClayAmbient rather than a glow welded into the mark: it is the same warm pool every
      // other screen sits on, so the hand-off from splash to dashboard no longer changes
      // the background under the user. It also fills the page, which is what keeps this
      // screen centred on a wide viewport.
      body: ClayAmbient(
        intensity: 0.9,
        child: SafeArea(
          child: LayoutBuilder(
            builder: (context, constraints) {
              final markSize =
                  math
                      .min(
                        constraints.maxWidth * _markWidthFraction,
                        constraints.maxHeight * _markHeightFraction,
                      )
                      .clamp(_markMin, _markMax);

              return Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(
                    maxWidth: _maxContentWidth,
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: ClaySpace.xxl,
                    ),
                    // The two states have very different heights, so they get different
                    // layouts rather than one compromise that overflows in the taller case.
                    child: hasError
                        ? _ErrorLayout(
                            markSize: markSize,
                            controller: _controller,
                            markFade: _markFade,
                            markScale: _markScale,
                            textFade: _textFade,
                            message: describeError(
                              session.error!,
                              AppL10n.of(context),
                            ),
                            onRetry: () => ref
                                .read(sessionControllerProvider.notifier)
                                .retry(),
                          )
                        : _LoadingLayout(
                            markSize: markSize,
                            available: constraints.maxHeight,
                            controller: _controller,
                            markFade: _markFade,
                            markScale: _markScale,
                            textFade: _textFade,
                            progressFade: _progressFade,
                          ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

/// Brand centred, progress line held near the bottom.
///
/// A Stack, not a Column with Spacers: the progress line has to sit low on a tall phone
/// without the brand drifting off a short landscape viewport. Space for the line is
/// RESERVED out of the centred area, so the two blocks can never collide however large the
/// system font is.
class _LoadingLayout extends StatelessWidget {
  const _LoadingLayout({
    required this.markSize,
    required this.available,
    required this.controller,
    required this.markFade,
    required this.markScale,
    required this.textFade,
    required this.progressFade,
  });

  final double markSize;
  final double available;
  final AnimationController controller;
  final Animation<double> markFade;
  final Animation<double> markScale;
  final Animation<double> textFade;
  final Animation<double> progressFade;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final textTheme = Theme.of(context).textTheme;

    // Measured, not guessed: the bar, its gap and one line of label at whatever scale the
    // user has chosen. A fixed 72 would be wrong the moment someone turns font size up.
    final labelHeight = MediaQuery.textScalerOf(context).scale(
      textTheme.labelSmall?.fontSize ?? 12,
    );
    final reserved = 3 + ClaySpace.md + (labelHeight * 1.4) + ClaySpace.xl;

    // On a very short viewport, reserving a fifth of it for a progress line starves the
    // brand. Cap the reservation so the mark always keeps the majority of the space.
    final bottomBand = math.min(reserved, available * 0.28);

    return Stack(
      children: [
        Positioned.fill(
          bottom: bottomBand,
          child: Center(
            child: _Brand(
              markSize: markSize,
              controller: controller,
              markFade: markFade,
              markScale: markScale,
              textFade: textFade,
            ),
          ),
        ),
        Positioned(
          left: 0,
          right: 0,
          bottom: ClaySpace.xl,
          child: AnimatedBuilder(
            animation: progressFade,
            builder: (context, child) =>
                Opacity(opacity: progressFade.value, child: child),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const _IndeterminateBar(),
                const SizedBox(height: ClaySpace.md),
                Text(
                  l10n.splashChecking,
                  style: textTheme.labelSmall,
                  textAlign: TextAlign.center,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

/// Brand above a banner and a Retry.
///
/// Scrollable, because this is the one state whose height is not under our control: the
/// failure message comes from the server or the socket, and in landscape at a large font
/// scale it will not fit. A splash that cannot show its own Retry button is a dead end, so
/// the content scrolls rather than overflowing.
class _ErrorLayout extends StatelessWidget {
  const _ErrorLayout({
    required this.markSize,
    required this.controller,
    required this.markFade,
    required this.markScale,
    required this.textFade,
    required this.message,
    required this.onRetry,
  });

  final double markSize;
  final AnimationController controller;
  final Animation<double> markFade;
  final Animation<double> markScale;
  final Animation<double> textFade;
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);

    return LayoutBuilder(
      builder: (context, constraints) => SingleChildScrollView(
        child: ConstrainedBox(
          // minHeight with an unbounded max is the idiom that makes `center` work when
          // there is room and lets the column grow past the fold when there is not.
          constraints: BoxConstraints(minHeight: constraints.maxHeight),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const SizedBox(height: ClaySpace.xl),
              _Brand(
                // Smaller here: the banner and button are the subject once something has
                // gone wrong, and the mark is only there for reassurance.
                markSize: markSize * 0.72,
                controller: controller,
                markFade: markFade,
                markScale: markScale,
                textFade: textFade,
              ),
              const SizedBox(height: ClaySpace.xxl),
              ClayEntrance(
                child: Column(
                  children: [
                    ClayBanner(
                      icon: Icons.cloud_off_rounded,
                      title: l10n.splashOfflineTitle,
                      // The specific failure, then the reassurance that the session
                      // survives it.
                      message: '$message\n\n${l10n.splashOfflineBody}',
                    ),
                    const SizedBox(height: ClaySpace.lg),
                    ClayButton(
                      label: l10n.actionRetry,
                      icon: Icons.refresh_rounded,
                      variant: ClayButtonVariant.primary,
                      expand: true,
                      onPressed: onRetry,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: ClaySpace.xl),
            ],
          ),
        ),
      ),
    );
  }
}

/// Mark, name, tagline — the animated brand block.
class _Brand extends StatelessWidget {
  const _Brand({
    required this.markSize,
    required this.controller,
    required this.markFade,
    required this.markScale,
    required this.textFade,
  });

  final double markSize;
  final AnimationController controller;
  final Animation<double> markFade;
  final Animation<double> markScale;
  final Animation<double> textFade;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final textTheme = Theme.of(context).textTheme;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Parallax. The mark rises further than the wordmark beneath it — different travel
        // over the same interval is what the eye reads as depth, and it costs one extra
        // Transform. Scale is on the mark only, so the text does not appear to zoom.
        AnimatedBuilder(
          animation: controller,
          builder: (context, child) => Opacity(
            // Floor at 0.55 rather than 0: a fade from fully transparent made the system
            // splash's mark disappear before this one was visible, which is the flicker
            // between the two screens.
            opacity: 0.55 + (0.45 * markFade.value),
            child: Transform.translate(
              offset: Offset(0, 18 * (1 - markScale.value)),
              child: Transform.scale(
                // 0.60 -> 1.0. The system splash renders the mark smaller than this one,
                // so starting partly scaled down means Flutter's first frame is close to
                // the size the platform left it at, and the growth reads as one continuous
                // motion rather than a jump between two screens showing the same logo.
                scale: 0.60 + (0.40 * markScale.value),
                child: child,
              ),
            ),
          ),
          child: _MarkImage(size: markSize),
        ),
        SizedBox(height: markSize * 0.08),
        AnimatedBuilder(
          animation: textFade,
          builder: (context, child) => Opacity(
            opacity: textFade.value,
            child: Transform.translate(
              offset: Offset(0, 10 * (1 - textFade.value)),
              child: child,
            ),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                l10n.appName,
                style: textTheme.headlineMedium,
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: ClaySpace.xs),
              Text(
                l10n.appTagline,
                style: textTheme.bodySmall,
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ],
    );
  }
}

/// The M-E wordmark.
///
/// Two files, not one recoloured at runtime: the supplied artwork has BLACK letterforms on
/// a transparent ground, which are invisible on the #050505 page. `logo_dark.png` is the
/// same mark with the letters mapped to white — the orange road is untouched, and because
/// the road's surface is transparent it picks up the dark page and reads as an unlit road
/// with orange markings.
///
/// A ColorFilter could not do this: it would recolour the orange too.
class _MarkImage extends StatelessWidget {
  const _MarkImage({required this.size});

  final double size;

  @override
  Widget build(BuildContext context) {
    final isDark = ClayTheme.of(context).palette.isDark;
    return Image.asset(
      isDark ? 'assets/images/logo_dark.png' : 'assets/images/logo_light.png',
      width: size,
      fit: BoxFit.contain,
      // The mark carries the app name visually; the name is announced by the text beneath
      // it, so repeating it here would make a screen reader say it twice.
      excludeFromSemantics: true,
    );
  }
}

/// A thin indeterminate bar.
///
/// Not a spinner: a spinner in the centre of a splash is the universal sign of an app that
/// is stuck. A 3px bar low on the page says "working" without claiming the screen.
class _IndeterminateBar extends StatelessWidget {
  const _IndeterminateBar();

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    return SizedBox(
      width: 132,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(ClayRadius.pill),
        child: LinearProgressIndicator(
          minHeight: 3,
          backgroundColor: palette.border,
          valueColor: AlwaysStoppedAnimation(palette.primary),
          // Under reduce-motion an indeterminate bar animates forever, which is exactly
          // what the setting exists to prevent. Pinned to a static partial fill instead.
          value: clayReduceMotion(context) ? 0.4 : null,
        ),
      ),
    );
  }
}
