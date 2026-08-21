import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:mtag_user_app/core/env/app_env.dart';
import 'package:mtag_user_app/core/models/vehicle.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/core/utils/money.dart';
import 'package:mtag_user_app/design_system/clay.dart';

/// A money figure.
///
/// Always through this widget, never a bare `Text('Rs. $x')`. It guarantees the two
/// things every balance in this app needs: tabular figures, so a refresh does not
/// make the number twitch, and a dash for null rather than a fabricated zero.
class MoneyText extends StatelessWidget {
  const MoneyText(
    this.amount, {
    this.style,
    this.color,
    this.textAlign,
    super.key,
  });

  final Decimal? amount;
  final TextStyle? style;
  final Color? color;
  final TextAlign? textAlign;

  @override
  Widget build(BuildContext context) {
    final resolved = (style ?? Theme.of(context).textTheme.titleMedium)!;
    return Text(
      Money.format(amount, locale: localeTag(context)),
      textAlign: textAlign,
      style: resolved.copyWith(
        color: color ?? resolved.color,
        // Belt and braces: the theme sets tabular figures on the display and label
        // styles, but a caller passing an arbitrary style would otherwise lose them.
        fontFeatures: const [FontFeature.tabularFigures()],
      ),
      // Digits are always LTR, even in an RTL layout. Without this an Urdu build
      // renders "Rs. 1,250" with the currency and digits in the wrong order.
      textDirection: TextDirection.ltr,
    );
  }
}

/// A signed amount for a transaction row: `− Rs. 120` in danger, `+ Rs. 1,000` in
/// success — with the sign carrying the meaning, not just the colour.
class SignedMoneyText extends StatelessWidget {
  const SignedMoneyText({
    required this.amount,
    required this.isCredit,
    this.style,
    super.key,
  });

  final Decimal? amount;
  final bool isCredit;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final resolved = (style ?? Theme.of(context).textTheme.titleMedium)!;
    return Text(
      Money.formatSigned(
        amount,
        isCredit: isCredit,
        locale: localeTag(context),
      ),
      style: resolved.copyWith(
        color: isCredit ? palette.successOnSurface : palette.dangerOnSurface,
        fontWeight: FontWeight.w700,
        fontFeatures: const [FontFeature.tabularFigures()],
      ),
      textDirection: TextDirection.ltr,
    );
  }
}

/// A balance with its urgency made explicit.
///
/// The colour is never the only signal — [BalanceLevel.blocked] gets a word and an
/// icon too, because the consequence (the barrier will not open) is too important to
/// encode in a hue that a colour-blind user cannot see and that clay's low contrast
/// weakens for everyone else.
class BalanceFigure extends StatelessWidget {
  const BalanceFigure({
    required this.amount,
    required this.level,
    this.style,
    this.showWarningIcon = true,
    super.key,
  });

  final Decimal? amount;
  final BalanceLevel level;
  final TextStyle? style;
  final bool showWarningIcon;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final color = switch (level) {
      BalanceLevel.blocked => palette.dangerOnSurface,
      BalanceLevel.low => palette.warningOnSurface,
      BalanceLevel.ok => palette.textPrimary,
      BalanceLevel.unknown => palette.textMuted,
    };

    final figure = MoneyText(amount, style: style, color: color);

    if (!showWarningIcon || level == BalanceLevel.ok) return figure;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          switch (level) {
            BalanceLevel.blocked => Icons.block_rounded,
            BalanceLevel.low => Icons.warning_amber_rounded,
            _ => Icons.help_outline_rounded,
          },
          size: 16,
          color: color,
        ),
        const SizedBox(width: ClaySpace.xs + 2),
        figure,
      ],
    );
  }
}

/// The minimum-entry gauge: how much of the Rs. 50 barrier threshold is covered.
class EntryReadinessRing extends StatelessWidget {
  const EntryReadinessRing({required this.balance, this.size = 64, super.key});

  final Decimal? balance;
  final double size;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final minimum = Money.fromInt(AppEnv.minimumEntryBalance);
    final value = balance == null
        ? 0.0
        : (balance! / minimum).toDouble().clamp(0.0, 1.0);
    final met = balance != null && balance! >= minimum;

    return ClayProgressRing(
      value: value,
      size: size,
      thickness: 8,
      color: met ? palette.success : palette.danger,
      semanticLabel: 'Entry minimum',
      child: Icon(
        met ? Icons.check_rounded : Icons.priority_high_rounded,
        size: size * 0.32,
        color: met ? palette.successOnSurface : palette.dangerOnSurface,
      ),
    );
  }
}
