import 'package:flutter/material.dart';
import 'package:mtag_user_app/design_system/clay/clay_surface.dart';
import 'package:mtag_user_app/design_system/theme/clay_theme.dart';
import 'package:mtag_user_app/design_system/tokens/clay_metrics.dart';

/// Semantic weight of a badge or pill.
enum ClayTone { neutral, primary, success, warning, danger }

/// Resolved colours for a tone: a soft fill for the pill and an AA-safe ink for
/// the text on top of it.
({Color fill, Color ink}) clayToneColors(BuildContext context, ClayTone tone) {
  final p = ClayTheme.of(context).palette;
  // The fill is the semantic colour at low alpha over the card, which keeps the
  // pill in the clay material rather than stamping a saturated sticker onto it.
  // The ink is the `…OnSurface` variant, which is the one that clears 4.5:1 —
  // the vivid fill colour would be 1.9:1 as small text.
  const a = 0.16;
  return switch (tone) {
    ClayTone.neutral => (
      fill: p.textMuted.withValues(alpha: 0.14),
      ink: p.textMuted,
    ),
    ClayTone.primary => (
      fill: p.primary.withValues(alpha: a),
      ink: p.primaryOnSurface,
    ),
    ClayTone.success => (
      fill: p.success.withValues(alpha: a),
      ink: p.successOnSurface,
    ),
    ClayTone.warning => (
      fill: p.warning.withValues(alpha: a),
      ink: p.warningOnSurface,
    ),
    ClayTone.danger => (
      fill: p.danger.withValues(alpha: a),
      ink: p.dangerOnSurface,
    ),
  };
}

/// A pill: rounded, soft-filled, always with a word in it.
///
/// Never colour alone — [label] is required and [icon] is encouraged. A green
/// dot means nothing to a colour-blind user, and clay's low contrast makes hue a
/// weak channel for everyone else too.
class ClayPill extends StatelessWidget {
  const ClayPill({
    required this.label,
    this.tone = ClayTone.neutral,
    this.icon,
    this.dense = false,
    super.key,
  });

  final String label;
  final ClayTone tone;
  final IconData? icon;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final colors = clayToneColors(context, tone);
    final textTheme = Theme.of(context).textTheme;

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: dense ? ClaySpace.sm + 2 : ClaySpace.md,
        vertical: dense ? ClaySpace.xs : ClaySpace.xs + 2,
      ),
      decoration: BoxDecoration(
        color: colors.fill,
        borderRadius: BorderRadius.circular(ClayRadius.pill),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: dense ? 12 : 14, color: colors.ink),
            const SizedBox(width: ClaySpace.xs + 2),
          ],
          // Flexible + ellipsis.
          //
          // `mainAxisSize.min` makes the pill hug its label, but it does NOT stop the
          // label from demanding more width than the parent has — a pill in a narrow
          // column (the "synced from booth" note inside a transaction row) simply
          // overflowed the screen edge. A pill is decoration around a label; when space
          // runs out the label must give, not the layout.
          Flexible(
            child: Text(
              label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: (dense ? textTheme.labelSmall : textTheme.labelMedium)
                  ?.copyWith(color: colors.ink, fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}

/// A raised chip, used for filters. Pressed when selected — a selected filter is
/// a switch that has been pushed in, which is a more literal reading of "active"
/// than a colour change.
class ClayFilterChip extends StatelessWidget {
  const ClayFilterChip({
    required this.label,
    required this.selected,
    required this.onTap,
    super.key,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;

    final content = Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: ClaySpace.lg,
        vertical: ClaySpace.sm + 2,
      ),
      child: Text(
        label,
        style: textTheme.labelMedium?.copyWith(
          color: selected ? palette.primaryOnSurface : palette.textMuted,
          fontWeight: FontWeight.w700,
        ),
      ),
    );

    return Semantics(
      button: true,
      selected: selected,
      label: label,
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: selected
            ? ClaySurface(
                style: ClayDepthStyle.pressed,
                radius: ClayRadius.pill,
                child: content,
              )
            : ClaySurface(
                depth: ClayDepth.control,
                radius: ClayRadius.pill,
                child: content,
              ),
      ),
    );
  }
}
