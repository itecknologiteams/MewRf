import 'package:flutter/material.dart';
import 'package:mtag_user_app/design_system/clay/clay_badge.dart';
import 'package:mtag_user_app/design_system/clay/clay_surface.dart';
import 'package:mtag_user_app/design_system/theme/clay_theme.dart';
import 'package:mtag_user_app/design_system/tokens/clay_metrics.dart';

/// A floating clay toast.
///
/// Material's SnackBar is a hard-edged bar pinned to the bottom, which is the one
/// shape this design system does not contain. This is the same content in a
/// raised clay pill, floating clear of the bottom nav so it never covers it.
void showClaySnack(
  BuildContext context, {
  required String message,
  ClayTone tone = ClayTone.neutral,
  IconData? icon,
  Duration duration = const Duration(seconds: 4),
  String? actionLabel,
  VoidCallback? onAction,
}) {
  final messenger = ScaffoldMessenger.maybeOf(context);
  if (messenger == null) return;

  final palette = ClayTheme.of(context).palette;
  final colors = clayToneColors(context, tone);
  final textTheme = Theme.of(context).textTheme;

  final resolvedIcon =
      icon ??
      switch (tone) {
        ClayTone.success => Icons.check_circle_outline_rounded,
        ClayTone.danger => Icons.error_outline_rounded,
        ClayTone.warning => Icons.warning_amber_rounded,
        _ => Icons.info_outline_rounded,
      };

  messenger
    ..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        duration: duration,
        behavior: SnackBarBehavior.floating,
        backgroundColor: Colors.transparent,
        elevation: 0,
        // Clear the bottom nav, which is itself inset from the bottom edge.
        margin: const EdgeInsets.fromLTRB(
          ClaySpace.gutter,
          0,
          ClaySpace.gutter,
          ClaySpace.xxl + ClaySpace.xl,
        ),
        padding: EdgeInsets.zero,
        content: ClaySurface(
          radius: ClayRadius.control,
          color: Color.alphaBlend(colors.fill, palette.surface),
          padding: const EdgeInsets.symmetric(
            horizontal: ClaySpace.lg,
            vertical: ClaySpace.lg,
          ),
          child: Row(
            children: [
              Icon(resolvedIcon, size: 20, color: colors.ink),
              const SizedBox(width: ClaySpace.md),
              Expanded(
                child: Text(
                  message,
                  style: textTheme.bodyMedium?.copyWith(
                    color: colors.ink,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              if (actionLabel != null && onAction != null)
                GestureDetector(
                  onTap: () {
                    messenger.hideCurrentSnackBar();
                    onAction();
                  },
                  child: Padding(
                    padding: const EdgeInsets.only(left: ClaySpace.md),
                    child: Text(
                      actionLabel,
                      style: textTheme.labelMedium?.copyWith(
                        color: colors.ink,
                        fontWeight: FontWeight.w700,
                        decoration: TextDecoration.underline,
                        decorationColor: colors.ink,
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
}
