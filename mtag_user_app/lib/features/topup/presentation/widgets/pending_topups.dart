import 'package:flutter/material.dart';
import 'package:mtag_user_app/core/models/topup.dart';
import 'package:mtag_user_app/core/utils/app_dates.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/core/utils/money.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Unsettled top-ups, shown above everything else on the top-up screen.
///
/// Prominent on purpose. Both working paths can leave one of these behind — the
/// aggregator flow settles via a callback the app never sees, and the app-initiated flow
/// has no checkout URL to complete — so a pending row is a normal state, not an
/// exception. A user who cannot see theirs concludes the first payment failed and pays
/// again.
class PendingTopups extends StatelessWidget {
  const PendingTopups({
    required this.pending,
    required this.onCheckAgain,
    super.key,
  });

  final List<TopupRequest> pending;
  final Future<void> Function() onCheckAgain;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;

    return ClayCard(
      color: Color.alphaBlend(
        palette.warning.withValues(alpha: 0.12),
        palette.surface,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.schedule_rounded,
                size: 18,
                color: palette.warningOnSurface,
              ),
              const SizedBox(width: ClaySpace.sm),
              Expanded(
                child: Text(
                  l10n.topupPendingListTitle,
                  style: textTheme.titleMedium?.copyWith(
                    color: palette.warningOnSurface,
                  ),
                ),
              ),
              ClayIconButton(
                icon: Icons.refresh_rounded,
                semanticLabel: l10n.actionRefresh,
                size: 36,
                iconSize: 17,
                onPressed: onCheckAgain,
              ),
            ],
          ),
          const SizedBox(height: ClaySpace.md),
          for (final topup in pending) ...[
            Row(
              children: [
                Expanded(
                  child: Text(
                    l10n.topupPendingRow(
                      Money.format(topup.amount, locale: localeTag(context)),
                    ),
                    style: textTheme.bodyMedium,
                  ),
                ),
                Text(
                  AppDates.relative(
                    topup.requestedAt,
                    locale: localeTag(context),
                  ),
                  style: textTheme.labelSmall,
                ),
              ],
            ),
            const SizedBox(height: ClaySpace.sm),
          ],
          const SizedBox(height: ClaySpace.xs),
          Text(l10n.topupTimedOutBody, style: textTheme.bodySmall),
        ],
      ),
    );
  }
}
