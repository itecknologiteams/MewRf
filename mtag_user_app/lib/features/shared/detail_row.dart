import 'package:flutter/material.dart';
import 'package:mtag_user_app/design_system/clay.dart';

/// A label/value pair.
///
/// Rows are separated by whitespace, never a `Divider` — this design system has no
/// hairlines, and a list of facts reads perfectly well on padding alone.
class DetailRow extends StatelessWidget {
  const DetailRow({
    required this.label,
    required this.value,
    this.monospace = false,
    this.valueColor,
    this.trailing,
    super.key,
  });

  final String label;
  final String value;

  /// For codes — serials, TIDs, reference ids. Proportional digits make `0`/`O` and
  /// `1`/`l` ambiguous in a string someone is about to read aloud or retype.
  final bool monospace;

  final Color? valueColor;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: ClaySpace.sm),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 116,
            child: Text(label, style: textTheme.labelMedium),
          ),
          const SizedBox(width: ClaySpace.md),
          Expanded(
            child: Text(
              value,
              style: monospace
                  ? textTheme.bodyMedium?.copyWith(
                      fontFamily: 'Mono',

                      letterSpacing: 0.6,
                      color: valueColor ?? palette.textPrimary,
                    )
                  : textTheme.bodyMedium?.copyWith(
                      color: valueColor ?? palette.textPrimary,
                    ),
              // A code keeps LTR order in an RTL layout.
              textDirection: monospace ? TextDirection.ltr : null,
            ),
          ),
          if (trailing != null) ...[
            const SizedBox(width: ClaySpace.sm),
            trailing!,
          ],
        ],
      ),
    );
  }
}
