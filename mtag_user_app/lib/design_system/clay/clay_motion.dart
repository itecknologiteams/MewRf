import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/core/utils/money.dart';
import 'package:mtag_user_app/design_system/theme/clay_theme.dart';
import 'package:mtag_user_app/design_system/tokens/clay_metrics.dart';

/// Motion primitives.
///
/// Everything here collapses to nothing under reduce-motion — via [clayDuration], not via
/// an `if` at each call site, so a new animation cannot forget to honour it.
///
/// The rule these follow: animation explains *what changed*, it does not decorate. A card
/// rises as it arrives so you can see it arrived. A balance counts up so you notice it
/// moved. Nothing bounces for its own sake, and nothing on a routine path costs more than
/// ~300ms, because this is an app people open at a barrier with a queue behind them.

/// Fades and lifts its child into place, optionally staggered by [index].
///
/// Used for cards entering a list. The lift is small (12px) and upward: it reads as
/// content settling onto the page rather than flying in.
class ClayEntrance extends StatefulWidget {
  const ClayEntrance({
    required this.child,
    this.index = 0,
    this.offset = 12,
    super.key,
  });

  final Widget child;

  /// Position in the list. Each item waits `index * ClayMotion.stagger` before starting.
  ///
  /// Capped internally, because a 200-row transaction list must not make row 60 wait three
  /// seconds — past the cap everything animates together.
  final int index;

  final double offset;

  @override
  State<ClayEntrance> createState() => _ClayEntranceState();
}

class _ClayEntranceState extends State<ClayEntrance>
    with SingleTickerProviderStateMixin {
  /// Beyond this, items animate as one group. See [ClayEntrance.index].
  static const _maxStaggered = 8;

  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: ClayMotion.enter,
  );

  late final Animation<double> _fade = CurvedAnimation(
    parent: _controller,
    curve: ClayMotion.ease,
  );

  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;

    if (clayReduceMotion(context)) {
      // Straight to the end state. No frames, no delay.
      _controller.value = 1;
      return;
    }

    final steps = widget.index.clamp(0, _maxStaggered);
    final delay = ClayMotion.stagger * steps;
    if (delay == Duration.zero) {
      _controller.forward();
    } else {
      Future<void>.delayed(delay, () {
        if (mounted) _controller.forward();
      });
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _fade,
      builder: (context, child) => Opacity(
        opacity: _fade.value,
        child: Transform.translate(
          offset: Offset(0, widget.offset * (1 - _fade.value)),
          child: child,
        ),
      ),
      child: widget.child,
    );
  }
}

/// A money figure that counts up when it changes.
///
/// The point is not decoration — it is that a balance changing is the single most
/// important event in this app, and a number that simply swaps is easy to miss. Counting
/// draws the eye to exactly the thing that moved.
///
/// It counts between two REAL server values. Nothing here invents a figure: the start is
/// the previous balance the server sent and the end is the new one, so every frame in
/// between is bounded by two truths. On first build it does not count at all — there is no
/// previous value to count from, and animating up from zero would imply a change that did
/// not happen.
class ClayAnimatedMoney extends StatefulWidget {
  const ClayAnimatedMoney(
    this.amount, {
    this.style,
    this.color,
    super.key,
  });

  final Decimal? amount;
  final TextStyle? style;
  final Color? color;

  @override
  State<ClayAnimatedMoney> createState() => _ClayAnimatedMoneyState();
}

class _ClayAnimatedMoneyState extends State<ClayAnimatedMoney>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: ClayMotion.count,
  );

  Decimal? _from;
  Decimal? _to;

  @override
  void initState() {
    super.initState();
    // First build shows the real figure immediately.
    _from = widget.amount;
    _to = widget.amount;
    _controller.value = 1;
  }

  @override
  void didUpdateWidget(ClayAnimatedMoney old) {
    super.didUpdateWidget(old);
    if (old.amount == widget.amount) return;

    _from = old.amount ?? widget.amount;
    _to = widget.amount;

    if (clayReduceMotion(context) || _from == null || _to == null) {
      _controller.value = 1;
      return;
    }
    _controller.forward(from: 0);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final resolved = widget.style ?? Theme.of(context).textTheme.displayLarge;

    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final from = _from;
        final to = _to;

        Decimal? current;
        if (to == null) {
          current = null;
        } else if (from == null || _controller.isCompleted) {
          current = to;
        } else {
          // Interpolated for DISPLAY only, then rounded to whole rupees. The value that
          // matters — the final one — is the server's exact Decimal, which is what lands
          // when the controller completes.
          final t = ClayMotion.ease.transform(_controller.value);
          final span = (to - from).toDouble();
          current = from + Decimal.parse((span * t).round().toString());
        }

        return Text(
          Money.format(current, locale: localeTag(context)),
          style: resolved?.copyWith(
            color: widget.color ?? resolved.color,
            fontFeatures: const [FontFeature.tabularFigures()],
          ),
          // Digits stay LTR even in an Urdu layout.
          textDirection: TextDirection.ltr,
        );
      },
    );
  }
}

/// Crossfades between the loading skeleton and the real content.
///
/// Without this, data landing makes the screen flick — skeleton gone, content in, on the
/// same frame. A 320ms crossfade makes it read as the content resolving into place, and
/// costs nothing because the data has already arrived.
class ClayContentSwitcher extends StatelessWidget {
  const ClayContentSwitcher({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return AnimatedSwitcher(
      duration: clayDuration(context, ClayMotion.enter),
      switchInCurve: ClayMotion.ease,
      switchOutCurve: ClayMotion.ease,
      // Fade only. A size transition here would make the whole page jump as the skeleton's
      // height gives way to the content's.
      layoutBuilder: (current, previous) => Stack(
        alignment: Alignment.topCenter,
        children: [...previous, ?current],
      ),
      child: child,
    );
  }
}

/// Scales its child down a hair while pressed.
///
/// The app's tactile feedback, now that surfaces no longer visibly sink. 0.97 is under the
/// threshold where it reads as an animation and just feels like the control gave.
class ClayPressable extends StatefulWidget {
  const ClayPressable({
    required this.child,
    required this.onTap,
    this.scale = 0.97,
    this.semanticLabel,
    super.key,
  });

  final Widget child;
  final VoidCallback? onTap;
  final double scale;
  final String? semanticLabel;

  @override
  State<ClayPressable> createState() => _ClayPressableState();
}

class _ClayPressableState extends State<ClayPressable> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    if (widget.onTap == null) return widget.child;

    return Semantics(
      button: true,
      label: widget.semanticLabel,
      child: GestureDetector(
        onTap: widget.onTap,
        onTapDown: (_) => setState(() => _down = true),
        onTapUp: (_) => setState(() => _down = false),
        // Cancel restores the resting state, so dragging off a control un-presses it —
        // which is what tells the user the tap will not fire.
        onTapCancel: () => setState(() => _down = false),
        behavior: HitTestBehavior.opaque,
        child: AnimatedScale(
          scale: _down ? widget.scale : 1,
          duration: clayPressDuration(context),
          curve: ClayMotion.ease,
          child: widget.child,
        ),
      ),
    );
  }
}

/// The page transition used for every pushed route.
///
/// A short fade with a small upward slide. Deliberately not a full horizontal push: this
/// app's pushed screens (Top Up, Vehicles, Trips) are details of what you were already
/// looking at, and a slide-over implies travelling somewhere else.
Widget clayPageTransition(
  BuildContext context,
  Animation<double> animation,
  Animation<double> secondaryAnimation,
  Widget child,
) {
  if (clayReduceMotion(context)) return child;

  final curved = CurvedAnimation(parent: animation, curve: ClayMotion.ease);
  return FadeTransition(
    opacity: curved,
    child: SlideTransition(
      position: Tween<Offset>(
        begin: const Offset(0, 0.03),
        end: Offset.zero,
      ).animate(curved),
      child: child,
    ),
  );
}
