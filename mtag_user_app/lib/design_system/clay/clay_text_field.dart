import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:mtag_user_app/design_system/clay/clay_surface.dart';
import 'package:mtag_user_app/design_system/theme/clay_theme.dart';
import 'package:mtag_user_app/design_system/tokens/clay_metrics.dart';

/// A text input carved into the surface.
///
/// Always [ClayDepthStyle.pressed] — never raised, never bordered. In clay an
/// input is a groove you type into, and the inset shadow is the only thing
/// telling the user this rectangle accepts text. An `OutlineInputBorder` here
/// would be the single most out-of-place pixel in the app, so the Material
/// decoration is stripped to `InputBorder.none` and the shape comes entirely
/// from the surface underneath.
class ClayTextField extends StatelessWidget {
  const ClayTextField({
    required this.controller,
    this.label,
    this.hint,
    this.errorText,
    this.keyboardType,
    this.textInputAction,
    this.obscureText = false,
    this.enabled = true,
    this.autofocus = false,
    this.maxLength,
    this.inputFormatters,
    this.prefixIcon,
    this.suffix,
    this.onSubmitted,
    this.onChanged,
    this.focusNode,
    this.autofillHints,
    this.textAlign = TextAlign.start,
    this.style,
    super.key,
  });

  final TextEditingController controller;
  final String? label;
  final String? hint;

  /// Field-level error, mapped straight from the envelope's `errors` map. Shown
  /// below the groove, in words, tinted with the AA-safe danger colour — never
  /// colour alone.
  final String? errorText;

  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final bool obscureText;
  final bool enabled;
  final bool autofocus;
  final int? maxLength;
  final List<TextInputFormatter>? inputFormatters;
  final IconData? prefixIcon;
  final Widget? suffix;
  final ValueChanged<String>? onSubmitted;
  final ValueChanged<String>? onChanged;
  final FocusNode? focusNode;
  final Iterable<String>? autofillHints;
  final TextAlign textAlign;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;
    final hasError = errorText != null && errorText!.isNotEmpty;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (label != null) ...[
          Padding(
            padding: const EdgeInsets.only(
              left: ClaySpace.xs,
              bottom: ClaySpace.sm,
            ),
            child: Text(label!, style: textTheme.labelMedium),
          ),
        ],
        ClaySurface(
          style: ClayDepthStyle.pressed,
          depth: ClayDepth.control,
          radius: ClayRadius.control,
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: ClaySpace.lg,
              vertical: ClaySpace.xs,
            ),
            child: Row(
              children: [
                if (prefixIcon != null) ...[
                  Icon(prefixIcon, size: 20, color: palette.textMuted),
                  const SizedBox(width: ClaySpace.md),
                ],
                Expanded(
                  child: TextField(
                    controller: controller,
                    focusNode: focusNode,
                    enabled: enabled,
                    autofocus: autofocus,
                    obscureText: obscureText,
                    keyboardType: keyboardType,
                    textInputAction: textInputAction,
                    maxLength: maxLength,
                    inputFormatters: inputFormatters,
                    onSubmitted: onSubmitted,
                    onChanged: onChanged,
                    autofillHints: autofillHints,
                    textAlign: textAlign,
                    cursorColor: palette.primary,
                    style: (style ?? textTheme.bodyLarge)?.copyWith(
                      color: enabled ? palette.textPrimary : palette.textMuted,
                    ),
                    decoration: InputDecoration(
                      hintText: hint,
                      hintStyle: textTheme.bodyLarge?.copyWith(
                        color: palette.textMuted.withValues(alpha: 0.7),
                      ),
                      // Every Material border switched off explicitly. Depth is
                      // the only separator in this design system.
                      border: InputBorder.none,
                      enabledBorder: InputBorder.none,
                      focusedBorder: InputBorder.none,
                      disabledBorder: InputBorder.none,
                      errorBorder: InputBorder.none,
                      focusedErrorBorder: InputBorder.none,
                      isDense: true,
                      counterText: '',
                      contentPadding: const EdgeInsets.symmetric(
                        vertical: ClaySpace.md + 2,
                      ),
                    ),
                  ),
                ),
                ?suffix,
              ],
            ),
          ),
        ),
        if (hasError)
          Padding(
            padding: const EdgeInsets.only(
              left: ClaySpace.xs,
              top: ClaySpace.sm,
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.error_outline_rounded,
                  size: 15,
                  color: palette.dangerOnSurface,
                ),
                const SizedBox(width: ClaySpace.xs + 2),
                Expanded(
                  child: Text(
                    errorText!,
                    style: textTheme.bodySmall?.copyWith(
                      color: palette.dangerOnSurface,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}
