import 'package:flutter/material.dart';
import 'package:mtag_user_app/design_system/clay/clay_surface.dart';
import 'package:mtag_user_app/design_system/theme/clay_theme.dart';
import 'package:mtag_user_app/design_system/tokens/clay_metrics.dart';

/// A bottom sheet as a slab of clay rising out of the page.
///
/// The grabber is a pressed pill rather than a drawn line — the same reason there
/// are no dividers anywhere else.
Future<T?> showClaySheet<T>({
  required BuildContext context,
  required WidgetBuilder builder,
  bool isScrollControlled = true,
  bool isDismissible = true,
}) {
  final palette = ClayTheme.of(context).palette;
  return showModalBottomSheet<T>(
    context: context,
    isScrollControlled: isScrollControlled,
    isDismissible: isDismissible,
    backgroundColor: Colors.transparent,
    elevation: 0,
    barrierColor: palette.isDark
        ? Colors.black.withValues(alpha: 0.6)
        : const Color(0xFF2B3550).withValues(alpha: 0.35),
    builder: (context) => ClaySheet(child: builder(context)),
  );
}

class ClaySheet extends StatelessWidget {
  const ClaySheet({required this.child, this.title, super.key});

  final Widget child;
  final String? title;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;

    return Padding(
      padding: EdgeInsets.only(
        left: ClaySpace.md,
        right: ClaySpace.md,
        bottom: MediaQuery.viewInsetsOf(context).bottom + ClaySpace.md,
      ),
      child: ClaySurface(
        depth: ClayDepth.hero,
        radius: ClayRadius.hero,
        color: palette.surface,
        padding: const EdgeInsets.fromLTRB(
          ClaySpace.cardPadding,
          ClaySpace.md,
          ClaySpace.cardPadding,
          ClaySpace.cardPadding,
        ),
        child: SafeArea(
          top: false,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Center(
                child: ClaySurface(
                  style: ClayDepthStyle.pressed,
                  depth: ClayDepth.nested,
                  radius: ClayRadius.pill,
                  width: 44,
                  height: 5,
                ),
              ),
              const SizedBox(height: ClaySpace.lg),
              if (title != null) ...[
                Text(title!, style: textTheme.titleLarge),
                const SizedBox(height: ClaySpace.lg),
              ],
              Flexible(child: child),
            ],
          ),
        ),
      ),
    );
  }
}
