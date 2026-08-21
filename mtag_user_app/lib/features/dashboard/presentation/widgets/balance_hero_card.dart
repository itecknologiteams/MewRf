import 'package:flutter/material.dart';
import 'package:mtag_user_app/core/data/wallet_repository.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// The hero: the loudest thing on any screen.
///
/// The label above the figure is not decoration — it is a correctness requirement.
/// **There is no single user balance in this system.** `Account` is a OneToOne on
/// `Vehicle`, so a holder with three vehicles has three independent wallets and cannot
/// spend one at another's plaza. This figure is a client-side sum, and presenting it
/// as "Your balance" would tell someone with Rs. 30 + Rs. 30 + Rs. 4,190 that they can
/// enter on any of their three tags, when two of them will be refused.
///
/// Hence: the count is in the label ("Total across 3 tags"), the explanation sits under
/// the figure, and the per-tag reality is one swipe away in the tag rail below.
class BalanceHeroCard extends StatelessWidget {
  const BalanceHeroCard({
    required this.total,
    required this.tagCount,
    required this.onTopUp,
    super.key,
  });

  final WalletTotal total;
  final int tagCount;
  final VoidCallback onTopUp;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;

    return ClayCard(
      // The one surface with a real backdrop blur: it sits directly over the upper
      // ambient pool, so there is genuinely something behind it to frost.
      blur: true,
      depth: ClayDepth.hero,
      radius: ClayRadius.hero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  l10n.dashboardTotalAcrossTags(total.walletCount),
                  style: textTheme.labelMedium,
                ),
              ),
              if (total.isPartial)
                const ClayPill(
                  label: '~',
                  tone: ClayTone.warning,
                  icon: Icons.warning_amber_rounded,
                  dense: true,
                ),
            ],
          ),
          const SizedBox(height: ClaySpace.sm),

          // Counts up when the figure changes — the one event in this app worth drawing
          // the eye to. It interpolates between two REAL server values and lands on the
          // exact Decimal; nothing is invented. See ClayAnimatedMoney.
          ClayAnimatedMoney(total.total, style: textTheme.displayLarge),

          const SizedBox(height: ClaySpace.sm),
          Text(
            total.isPartial
                // A sum computed over a set that included an unreadable balance is a
                // FLOOR. Saying so matters more than the tidier label: too high is the
                // direction that tells someone they can enter when they cannot.
                ? l10n.dashboardTotalPartial
                : l10n.dashboardTotalIsASum,
            style: textTheme.bodySmall?.copyWith(
              color: total.isPartial
                  ? palette.warningOnSurface
                  : palette.textMuted,
            ),
          ),

          const SizedBox(height: ClaySpace.xl),
          ClayButton(
            label: l10n.actionTopUp,
            icon: Icons.add_rounded,
            variant: ClayButtonVariant.primary,
            expand: true,
            onPressed: onTopUp,
          ),
        ],
      ),
    );
  }
}
