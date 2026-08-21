import 'dart:ui' show ImageFilter;

import 'package:flutter/material.dart';
import 'package:mtag_user_app/design_system/theme/clay_theme.dart';
import 'package:mtag_user_app/design_system/tokens/clay_metrics.dart';

class ClayNavItem {
  const ClayNavItem({
    required this.icon,
    required this.activeIcon,
    required this.label,
  });

  /// Outline, for the unselected state.
  final IconData icon;

  /// Filled, for the selected one.
  ///
  /// Weight carries the selection as well as colour. An outline icon merely turning orange
  /// is a hue-only signal, which is the thing this design system forbids everywhere else.
  final IconData activeIcon;

  final String label;
}

/// iOS-style bottom navigation: a translucent blurred bar with a hairline along its top,
/// and one optionally prominent centre action.
///
/// **This is one of the few places a real [BackdropFilter] earns its cost.** Content
/// scrolls underneath a fixed bar, so there is genuinely something moving behind the glass
/// — unlike a card in a list, where the blur samples a flat field and changes nothing. It
/// is also a single surface for the whole app rather than one per row.
///
/// The prominent item is a filled circular button that breaks the bar's top edge. That
/// overlap is what makes it read as the primary action rather than as a fifth tab: it is
/// literally on a different plane from its neighbours.
class ClayBottomNav extends StatelessWidget {
  const ClayBottomNav({
    required this.items,
    required this.currentIndex,
    required this.onTap,
    this.prominentIndex,
    super.key,
  });

  final List<ClayNavItem> items;
  final int currentIndex;
  final ValueChanged<int> onTap;

  /// Index rendered as a raised circular action. Null for a flat bar.
  final int? prominentIndex;

  /// How far the prominent button rises above the bar.
  static const _lift = 18.0;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;

    final bar = ClipRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(
          sigmaX: ClayBlur.pane,
          sigmaY: ClayBlur.pane,
        ),
        child: DecoratedBox(
          decoration: BoxDecoration(
            // Translucent, not opaque — the blur has to have something to show through.
            color: palette.surface.withValues(alpha: 0.72),
            border: Border(top: BorderSide(color: palette.border)),
          ),
          child: SafeArea(
            top: false,
            child: SizedBox(
              height: 58,
              child: Row(
                children: [
                  for (var i = 0; i < items.length; i++)
                    Expanded(
                      child: i == prominentIndex
                          // The prominent button is painted in the overlay below so it can
                          // escape the bar's bounds; this reserves its column.
                          ? const SizedBox.shrink()
                          : _NavButton(
                              item: items[i],
                              selected: i == currentIndex,
                              onTap: () => onTap(i),
                            ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );

    if (prominentIndex == null) return bar;

    // Stack, with the bar's own height plus the lift, so the circle can overhang the top
    // edge without being clipped.
    return SizedBox(
      height: 58 + _lift + MediaQuery.viewPaddingOf(context).bottom,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Positioned(left: 0, right: 0, bottom: 0, child: bar),
          Positioned(
            bottom: MediaQuery.viewPaddingOf(context).bottom + 12,
            left: 0,
            right: 0,
            child: Center(
              child: _ProminentButton(
                item: items[prominentIndex!],
                selected: currentIndex == prominentIndex,
                onTap: () => onTap(prominentIndex!),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  const _NavButton({
    required this.item,
    required this.selected,
    required this.onTap,
  });

  final ClayNavItem item;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;
    final duration = clayDuration(context, ClayMotion.press);
    final ink = selected ? palette.primary : palette.textMuted;

    return Semantics(
      button: true,
      selected: selected,
      label: item.label,
      child: GestureDetector(
        onTap: onTap,
        // Opaque so the whole column is tappable — a 22px glyph alone is well under the
        // 48dp minimum target.
        behavior: HitTestBehavior.opaque,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AnimatedScale(
              scale: selected ? 1.08 : 1,
              duration: duration,
              curve: ClayMotion.ease,
              child: Icon(
                selected ? item.activeIcon : item.icon,
                size: 22,
                color: ink,
              ),
            ),
            const SizedBox(height: 4),
            AnimatedDefaultTextStyle(
              duration: duration,
              curve: ClayMotion.ease,
              style:
                  textTheme.labelSmall?.copyWith(
                    color: ink,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w600,
                  ) ??
                  const TextStyle(),
              child: Text(
                item.label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// The raised centre action.
///
/// Solid orange with a coloured glow beneath it — the one place in the app where the
/// accent fills a whole shape, which is what buys it the "primary action" read inside the
/// 70/20/10 budget.
class _ProminentButton extends StatefulWidget {
  const _ProminentButton({
    required this.item,
    required this.selected,
    required this.onTap,
  });

  final ClayNavItem item;
  final bool selected;
  final VoidCallback onTap;

  @override
  State<_ProminentButton> createState() => _ProminentButtonState();
}

class _ProminentButtonState extends State<_ProminentButton> {
  bool _down = false;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;

    return Semantics(
      button: true,
      selected: widget.selected,
      label: widget.item.label,
      child: GestureDetector(
        onTap: widget.onTap,
        onTapDown: (_) => setState(() => _down = true),
        onTapUp: (_) => setState(() => _down = false),
        onTapCancel: () => setState(() => _down = false),
        behavior: HitTestBehavior.opaque,
        child: AnimatedScale(
          scale: _down ? 0.93 : 1,
          duration: clayPressDuration(context),
          curve: ClayMotion.ease,
          child: Container(
            width: 58,
            height: 58,
            decoration: BoxDecoration(
              color: palette.primary,
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: palette.primary.withValues(alpha: 0.34),
                  offset: const Offset(0, 6),
                  blurRadius: 18,
                ),
                BoxShadow(
                  color: palette.shadow,
                  offset: const Offset(0, 2),
                  blurRadius: 6,
                ),
              ],
            ),
            child: Icon(
              widget.item.activeIcon,
              size: 26,
              color: palette.onPrimary,
            ),
          ),
        ),
      ),
    );
  }
}
