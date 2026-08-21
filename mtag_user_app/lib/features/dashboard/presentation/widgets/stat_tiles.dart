import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mtag_user_app/core/router/app_router.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/core/utils/money.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/dashboard/presentation/wallet_controller.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Tags · Vehicles · Tolls this month.
///
/// "Tags" is the count of the user's vehicles that HAVE a tag row, not the count of
/// vehicles — a vehicle mid-reissue has none, and conflating the two would report a
/// tag the user cannot use.
class StatTiles extends ConsumerWidget {
  const StatTiles({required this.snapshot, super.key});

  final WalletSnapshot snapshot;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppL10n.of(context);
    final summary = snapshot.summary;

    // IntrinsicHeight, and it is load-bearing rather than cosmetic.
    //
    // The three tiles must be equal height regardless of which one wraps to two lines, and
    // `CrossAxisAlignment.stretch` is the natural way to say that. But this Row lives in
    // the dashboard's vertical ListView, where the CROSS axis is vertical and UNBOUNDED —
    // so `stretch` asks each tile to be infinitely tall and throws "BoxConstraints forces
    // an infinite height". The ListView's sliver then fails its `child.hasSize` assertion
    // and the ENTIRE dashboard renders blank, with no error box on screen to say why.
    //
    // IntrinsicHeight measures the tallest child first and bounds the Row to it, so stretch
    // has something finite to stretch to. It costs an extra layout pass over three small
    // tiles, which is nothing.
    //
    // Covered by test/features/dashboard_layout_test.dart.
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: _StatTile(
              icon: Icons.sensors_rounded,
              label: l10n.dashboardStatTags,
              value: '${snapshot.vehiclesWithTags.length}',
              onTap: () => context.go(Routes.tags),
            ),
          ),
          const SizedBox(width: ClaySpace.md),
          Expanded(
            child: _StatTile(
              icon: Icons.directions_car_rounded,
              label: l10n.dashboardStatVehicles,
              value: '${snapshot.vehicles.length}',
              onTap: () => context.push(Routes.vehicles),
            ),
          ),
          const SizedBox(width: ClaySpace.md),
          Expanded(
            child: _StatTile(
              icon: Icons.toll_rounded,
              label: l10n.dashboardStatMonthTolls,
              value: summary == null
                  ? l10n.unknownValue
                  : Money.format(
                      summary.monthTollTotal,
                      locale: localeTag(context),
                    ),
              // The client-side fallback aggregates over one transaction page per
              // account, so for a heavy user the month total is a lower bound. Marked
              // "at least" rather than presented as exact — a month's tolls is a figure
              // people budget against.
              prefix: (summary?.isPartial ?? false)
                  ? l10n.dashboardStatMonthTollsPartial
                  : null,
              onTap: () => context.go(Routes.activity),
            ),
          ),
        ],
      ),
    );
  }
}

class _StatTile extends StatelessWidget {
  const _StatTile({
    required this.icon,
    required this.label,
    required this.value,
    this.prefix,
    this.onTap,
  });

  final IconData icon;
  final String label;
  final String value;
  final String? prefix;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;

    return ClayCard(
      onTap: onTap,
      depth: ClayDepth.control,
      semanticLabel: '$label: $value',
      padding: const EdgeInsets.symmetric(
        horizontal: ClaySpace.md,
        vertical: ClaySpace.lg,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 20, color: palette.primaryOnSurface),
          const SizedBox(height: ClaySpace.md),
          if (prefix != null)
            Text(
              prefix!,
              style: textTheme.labelSmall,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          Text(
            value,
            style: textTheme.titleLarge?.copyWith(
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            // A figure is LTR even in an Urdu layout.
            textDirection: TextDirection.ltr,
          ),
          const SizedBox(height: ClaySpace.xs),
          Text(
            label,
            style: textTheme.labelSmall,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}
