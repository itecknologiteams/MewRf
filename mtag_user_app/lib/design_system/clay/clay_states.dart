import 'package:flutter/material.dart';
import 'package:mtag_user_app/design_system/clay/clay_badge.dart';
import 'package:mtag_user_app/design_system/clay/clay_button.dart';
import 'package:mtag_user_app/design_system/clay/clay_surface.dart';
import 'package:mtag_user_app/design_system/theme/clay_theme.dart';
import 'package:mtag_user_app/design_system/tokens/clay_metrics.dart';

/// The empty state.
///
/// Always carries a next action when one exists. "No transactions yet" is a dead
/// end; "No transactions yet — they appear here after your first trip" tells the
/// user nothing is broken, which is the actual question they are asking.
class ClayEmptyState extends StatelessWidget {
  const ClayEmptyState({
    required this.icon,
    required this.title,
    this.message,
    this.actionLabel,
    this.onAction,
    this.tone = ClayTone.primary,
    super.key,
  });

  final IconData icon;
  final String title;
  final String? message;
  final String? actionLabel;
  final VoidCallback? onAction;
  final ClayTone tone;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final colors = clayToneColors(context, tone);

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(ClaySpace.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // A pressed disc: the illustration is a dimple in the page rather
            // than a sticker on it, which is the same material logic as the
            // inputs.
            ClaySurface(
              style: ClayDepthStyle.clay,
              radius: ClayRadius.pill,
              width: 96,
              height: 96,
              child: Center(child: Icon(icon, size: 38, color: colors.ink)),
            ),
            const SizedBox(height: ClaySpace.xl),
            Text(
              title,
              textAlign: TextAlign.center,
              style: textTheme.titleLarge,
            ),
            if (message != null) ...[
              const SizedBox(height: ClaySpace.sm),
              Text(
                message!,
                textAlign: TextAlign.center,
                style: textTheme.bodyMedium?.copyWith(
                  color: ClayTheme.of(context).palette.textMuted,
                ),
              ),
            ],
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: ClaySpace.xl),
              ClayButton(
                label: actionLabel!,
                onPressed: onAction,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// The error state. Message plus Retry, every time.
class ClayErrorState extends StatelessWidget {
  const ClayErrorState({
    required this.message,
    required this.onRetry,
    this.retryLabel,
    this.title,
    super.key,
  });

  final String message;
  final VoidCallback? onRetry;
  final String? retryLabel;
  final String? title;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final palette = ClayTheme.of(context).palette;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(ClaySpace.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ClaySurface(
              style: ClayDepthStyle.clay,
              radius: ClayRadius.pill,
              width: 96,
              height: 96,
              child: Center(
                child: Icon(
                  Icons.cloud_off_rounded,
                  size: 38,
                  color: palette.dangerOnSurface,
                ),
              ),
            ),
            const SizedBox(height: ClaySpace.xl),
            if (title != null) ...[
              Text(
                title!,
                textAlign: TextAlign.center,
                style: textTheme.titleLarge,
              ),
              const SizedBox(height: ClaySpace.sm),
            ],
            Text(
              message,
              textAlign: TextAlign.center,
              style: textTheme.bodyMedium?.copyWith(color: palette.textMuted),
            ),
            if (onRetry != null) ...[
              const SizedBox(height: ClaySpace.xl),
              ClayButton(
                label: retryLabel ?? 'Retry',
                icon: Icons.refresh_rounded,
                onPressed: onRetry,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// The "you are looking at saved data" ribbon.
///
/// Mandatory above any cached balance. A balance is a number the user will make a
/// decision on — whether to top up before entering — and a stale one shown
/// without its age is worse than no number at all, because it looks current.
class ClayStaleRibbon extends StatelessWidget {
  const ClayStaleRibbon({
    required this.message,
    this.onRefresh,
    this.tone = ClayTone.warning,
    super.key,
  });

  final String message;
  final VoidCallback? onRefresh;
  final ClayTone tone;

  @override
  Widget build(BuildContext context) {
    final colors = clayToneColors(context, tone);
    final textTheme = Theme.of(context).textTheme;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
        horizontal: ClaySpace.lg,
        vertical: ClaySpace.md,
      ),
      decoration: BoxDecoration(
        color: colors.fill,
        borderRadius: BorderRadius.circular(ClayRadius.control),
      ),
      child: Row(
        children: [
          Icon(Icons.history_rounded, size: 17, color: colors.ink),
          const SizedBox(width: ClaySpace.md),
          Expanded(
            child: Text(
              message,
              style: textTheme.bodySmall?.copyWith(
                color: colors.ink,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          if (onRefresh != null)
            GestureDetector(
              onTap: onRefresh,
              child: Padding(
                padding: const EdgeInsets.only(left: ClaySpace.sm),
                child: Icon(Icons.refresh_rounded, size: 18, color: colors.ink),
              ),
            ),
        ],
      ),
    );
  }
}

/// An inline banner: low balance, pending payment, a stubbed feature.
class ClayBanner extends StatelessWidget {
  const ClayBanner({
    required this.icon,
    required this.title,
    this.message,
    this.tone = ClayTone.warning,
    this.actionLabel,
    this.onAction,
    super.key,
  });

  final IconData icon;
  final String title;
  final String? message;
  final ClayTone tone;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    final colors = clayToneColors(context, tone);
    final textTheme = Theme.of(context).textTheme;

    return ClaySurface(
      depth: ClayDepth.control,
      color: Color.alphaBlend(
        colors.fill,
        ClayTheme.of(context).palette.surface,
      ),
      padding: const EdgeInsets.all(ClaySpace.lg),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 22, color: colors.ink),
          const SizedBox(width: ClaySpace.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: textTheme.titleMedium?.copyWith(color: colors.ink),
                ),
                if (message != null) ...[
                  const SizedBox(height: ClaySpace.xs),
                  Text(
                    message!,
                    style: textTheme.bodySmall?.copyWith(color: colors.ink),
                  ),
                ],
                if (actionLabel != null && onAction != null) ...[
                  const SizedBox(height: ClaySpace.md),
                  ClayButton(
                    label: actionLabel!,
                    onPressed: onAction,
                    padding: const EdgeInsets.symmetric(
                      horizontal: ClaySpace.lg,
                      vertical: ClaySpace.md,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
