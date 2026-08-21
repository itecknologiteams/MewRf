import 'package:flutter/material.dart';
import 'package:mtag_user_app/core/models/account.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/utils/app_dates.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/core/utils/money.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/shared/money_text.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// One transaction.
///
/// Flat, not raised: it sits inside a card that is already raised, and a second shadow
/// pair inside one produces mud rather than depth. It is also why a 200-row list stays
/// cheap — see the perf note in the design system.
class TransactionRow extends StatelessWidget {
  const TransactionRow({
    required this.transaction,
    this.showPlate = false,
    this.onTap,
    super.key,
  });

  final Transaction transaction;

  /// On for the merged dashboard feed and the all-accounts activity list, where the
  /// plate is the only thing distinguishing two identical fares.
  final bool showPlate;

  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;
    final isCredit = transaction.isCredit;

    final subtitleParts = <String>[
      AppDates.time(transaction.processedAt, locale: localeTag(context)),
      if (showPlate && (transaction.plateNumber?.isNotEmpty ?? false))
        transaction.plateNumber!,
    ];

    return InkWell(
      onTap: onTap,
      // No Material ink — the design system has no ripple, and a splash on a clay
      // surface reads as a rendering glitch.
      splashFactory: NoSplash.splashFactory,
      highlightColor: Colors.transparent,
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: ClaySpace.lg,
          vertical: ClaySpace.md,
        ),
        child: Row(
          children: [
            // A pressed disc: the icon is carved into the card rather than stamped on.
            ClaySurface(
              style: ClayDepthStyle.pressed,
              depth: ClayDepth.nested,
              radius: ClayRadius.pill,
              width: 40,
              height: 40,
              child: Center(
                child: Icon(
                  _iconFor(transaction.type),
                  size: 18,
                  color: isCredit
                      ? palette.successOnSurface
                      : palette.dangerOnSurface,
                ),
              ),
            ),
            const SizedBox(width: ClaySpace.md),
            // 3:2 against the trailing column.
            //
            // Both sides must be flex, and both must ellipsize. The trailing column used
            // to be unconstrained, so "Balance: Rs. 12,345" claimed its full intrinsic
            // width and shoved the row past the screen edge — 197px over at 420 logical,
            // and worse on the narrower phones this ships to. Fixed ratios also survive a
            // large text scale, which a hardcoded maxWidth would not.
            Expanded(
              flex: 3,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    transaction.type.label(l10n),
                    style: textTheme.titleMedium,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    subtitleParts.join(' · '),
                    style: textTheme.bodySmall,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),

                  // The "synced from booth" note.
                  //
                  // A booth can run offline and syncs every 30s, so this charge may have
                  // reached the server long after the driver exited. Without this note a
                  // toll appearing twenty minutes late looks like a double charge or a
                  // mistake, and it is neither.
                  if (transaction.wasSyncedFromBooth) ...[
                    const SizedBox(height: ClaySpace.xs),
                    ClayPill(
                      label: l10n.transactionSyncedFromBooth,
                      icon: Icons.sync_rounded,
                      dense: true,
                    ),
                  ],

                  // A failed or pending row must never look settled — a pending top-up
                  // shown like a completed one is a user who thinks they have money.
                  if (transaction.status == TransactionStatus.failed) ...[
                    const SizedBox(height: ClaySpace.xs),
                    ClayPill(
                      label: l10n.transactionStatusFailed,
                      tone: ClayTone.danger,
                      icon: Icons.error_outline_rounded,
                      dense: true,
                    ),
                  ] else if (transaction.status ==
                      TransactionStatus.pending) ...[
                    const SizedBox(height: ClaySpace.xs),
                    ClayPill(
                      label: l10n.transactionStatusPending,
                      tone: ClayTone.warning,
                      icon: Icons.schedule_rounded,
                      dense: true,
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(width: ClaySpace.md),
            Expanded(
              flex: 2,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  SignedMoneyText(
                    amount: transaction.amount,
                    isCredit: isCredit,
                    style: textTheme.titleMedium,
                  ),
                  if (transaction.balanceAfter != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      l10n.transactionBalanceAfter(
                        Money.format(
                          transaction.balanceAfter,
                          locale: localeTag(context),
                        ),
                      ),
                      style: textTheme.labelSmall,
                      maxLines: 1,
                      // Ellipsis, not just maxLines. maxLines alone still asks for the
                      // full intrinsic width and simply clips — which is what overflowed.
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.end,
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  static IconData _iconFor(TransactionType type) => switch (type) {
    TransactionType.tollDeduction => Icons.toll_rounded,
    TransactionType.topup => Icons.add_circle_outline_rounded,
    TransactionType.refund => Icons.replay_rounded,
    TransactionType.transferIn => Icons.south_west_rounded,
    TransactionType.transferOut => Icons.north_east_rounded,
    TransactionType.unknown => Icons.receipt_long_rounded,
  };
}

/// A sticky day header.
///
/// The day is computed in **PKT**, not the device zone. On a phone set to UTC a
/// Karachi evening splits across two headings, and a driver looking for "yesterday's
/// trip" would find it filed under the day before.
class DayHeader extends StatelessWidget {
  const DayHeader({required this.day, super.key});

  final DateTime day;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    return Container(
      // Opaque, so rows scrolling underneath a pinned header do not show through.
      color: palette.base,
      padding: const EdgeInsets.only(
        top: ClaySpace.lg,
        bottom: ClaySpace.sm,
      ),
      child: Text(
        AppDates.dayHeader(day, locale: localeTag(context)),
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
          fontWeight: FontWeight.w700,
          color: palette.textMuted,
        ),
      ),
    );
  }
}
