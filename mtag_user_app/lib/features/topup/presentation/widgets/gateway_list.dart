import 'package:flutter/material.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/topup/domain/payment_gateway.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// The payment methods, each carrying an honest availability badge.
///
/// The badges are the point. Four of the five methods are not simply "available":
///
///   * JazzCash app — **Works now.** The only end-to-end path.
///   * Pay in this app — **Not set up**, unless a checkout URL is configured.
///   * Cash at a booth — Works now (it is information, not a transaction).
///   * Easypaisa, Card — **Coming soon.** No backend of any kind.
///
/// A method that cannot take a payment is still tappable, because tapping it explains
/// why and offers the path that works. What it must never be is a button that looks
/// live and silently does nothing.
class GatewayList extends StatelessWidget {
  const GatewayList({
    required this.selectedId,
    required this.gatewayContext,
    required this.onSelect,
    super.key,
  });

  final String? selectedId;
  final GatewayContext gatewayContext;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        for (final gateway in paymentGateways) ...[
          _GatewayTile(
            gateway: gateway,
            availability: gateway.availabilityFor(gatewayContext),
            selected: gateway.id == selectedId,
            onTap: () => onSelect(gateway.id),
          ),
          const SizedBox(height: ClaySpace.md),
        ],
      ],
    );
  }
}

class _GatewayTile extends StatelessWidget {
  const _GatewayTile({
    required this.gateway,
    required this.availability,
    required this.selected,
    required this.onTap,
  });

  final PaymentGateway gateway;
  final GatewayAvailability availability;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;

    final (String title, String subtitle, IconData icon) = switch (gateway) {
      JazzCashAggregatorGateway() => (
        l10n.topupMethodJazzCashApp,
        l10n.topupMethodJazzCashAppSubtitle,
        Icons.smartphone_rounded,
      ),
      JazzCashCheckoutGateway() => (
        l10n.topupMethodJazzCashCheckout,
        l10n.topupMethodJazzCashCheckoutSubtitle,
        Icons.lock_outline_rounded,
      ),
      CashAtBoothGateway() => (
        l10n.topupMethodCash,
        l10n.topupMethodCashSubtitle,
        Icons.payments_outlined,
      ),
      EasypaisaGateway() => (
        l10n.topupMethodEasypaisa,
        l10n.topupMethodEasypaisaSubtitle,
        Icons.account_balance_wallet_outlined,
      ),
      CardGateway() => (
        l10n.topupMethodCard,
        l10n.topupMethodCardSubtitle,
        Icons.credit_card_rounded,
      ),
      _ => (gateway.id, '', Icons.help_outline_rounded),
    };

    final (
      String badge,
      ClayTone tone,
      IconData badgeIcon,
    ) = switch (availability) {
      GatewayAvailability.available => (
        l10n.topupBadgeWorksNow,
        ClayTone.success,
        Icons.check_circle_outline_rounded,
      ),
      GatewayAvailability.comingSoon => (
        l10n.topupBadgeComingSoon,
        ClayTone.neutral,
        Icons.schedule_rounded,
      ),
      GatewayAvailability.notConfigured => (
        l10n.topupBadgeUnavailable,
        ClayTone.warning,
        Icons.build_outlined,
      ),
    };

    final dimmed = availability != GatewayAvailability.available;

    return ClayCard(
      onTap: onTap,
      depth: selected ? ClayDepth.nested : ClayDepth.control,
      semanticLabel: '$title, $badge',
      padding: const EdgeInsets.all(ClaySpace.lg),
      child: Row(
        children: [
          ClaySurface(
            style: selected ? ClayDepthStyle.raised : ClayDepthStyle.pressed,
            depth: ClayDepth.nested,
            radius: ClayRadius.pill,
            width: 44,
            height: 44,
            child: Center(
              child: Icon(
                icon,
                size: 20,
                color: dimmed
                    ? palette.textMuted
                    : (selected
                          ? palette.primaryOnSurface
                          : palette.textPrimary),
              ),
            ),
          ),
          const SizedBox(width: ClaySpace.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: textTheme.titleMedium?.copyWith(
                    color: dimmed ? palette.textMuted : palette.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: textTheme.bodySmall,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          const SizedBox(width: ClaySpace.sm),
          ClayPill(label: badge, tone: tone, icon: badgeIcon, dense: true),
        ],
      ),
    );
  }
}
