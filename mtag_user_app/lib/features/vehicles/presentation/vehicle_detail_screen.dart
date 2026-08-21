import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/vehicle.dart';
import 'package:mtag_user_app/core/router/app_router.dart';
import 'package:mtag_user_app/core/utils/app_dates.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/dashboard/presentation/wallet_controller.dart';
import 'package:mtag_user_app/features/shared/detail_row.dart';
import 'package:mtag_user_app/features/shared/money_text.dart';
import 'package:mtag_user_app/features/shared/tag_status_badge.dart';
import 'package:mtag_user_app/features/trips/presentation/trips_controller.dart';
import 'package:mtag_user_app/features/trips/presentation/widgets/trip_card.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

class VehicleDetailScreen extends ConsumerWidget {
  const VehicleDetailScreen({required this.vehicleId, super.key});

  final int vehicleId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppL10n.of(context);
    final textTheme = Theme.of(context).textTheme;
    final vehicle = ref.watch(vehicleByIdProvider(vehicleId));

    if (vehicle == null) {
      return ClayScaffold(
        title: l10n.vehiclesTitle,
        showBack: true,
        body: ClayEmptyState(
          icon: Icons.search_off_rounded,
          title: l10n.errorNotFound,
          message: l10n.vehiclesEmptyBody,
          actionLabel: l10n.actionBack,
          onAction: () => context.pop(),
        ),
      );
    }

    final trips = ref.watch(vehicleTripsProvider(vehicleId));

    return ClayScaffold(
      title: vehicle.plateNumber,
      subtitle: vehicle.vehicleType.label(l10n),
      showBack: true,
      body: ListView(
        padding: const EdgeInsets.only(bottom: ClaySpace.xxl),
        children: [
          ClayCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            l10n.vehicleBalance,
                            style: textTheme.labelMedium,
                          ),
                          const SizedBox(height: ClaySpace.xs),
                          BalanceFigure(
                            amount: vehicle.balance,
                            level: vehicle.balanceLevel,
                            style: textTheme.displayMedium,
                            showWarningIcon: false,
                          ),
                        ],
                      ),
                    ),
                    EntryReadinessRing(balance: vehicle.balance, size: 58),
                  ],
                ),
                const SizedBox(height: ClaySpace.lg),
                ClayButton(
                  label: l10n.actionTopUp,
                  icon: Icons.add_rounded,
                  variant: ClayButtonVariant.primary,
                  expand: true,
                  onPressed: vehicle.accountId == null
                      ? null
                      : () => context.push(
                          Routes.topupPath(accountId: vehicle.accountId),
                        ),
                ),
              ],
            ),
          ),
          const SizedBox(height: ClaySpace.cardGap),

          ClayCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(child: PlateNumber(vehicle.plateNumber)),
                    TagStatusBadge(tag: vehicle.tag, dense: true),
                  ],
                ),
                const SizedBox(height: ClaySpace.lg),
                DetailRow(
                  label: l10n.vehicleFareClass,
                  value: vehicle.vehicleType.label(l10n),
                ),
                DetailRow(
                  label: l10n.vehicleStatus,
                  value: vehicle.status.label(l10n),
                ),
                DetailRow(
                  label: l10n.vehicleRegistered,
                  value: AppDates.date(
                    vehicle.registeredAt,
                    locale: localeTag(context),
                  ),
                ),

                // A motorcycle is a valid registration class but is not permitted on the
                // expressway. Said plainly here rather than left for the driver to
                // discover at a barrier.
                if (vehicle.vehicleType == VehicleType.motorcycle) ...[
                  const SizedBox(height: ClaySpace.md),
                  ClayBanner(
                    icon: Icons.do_not_disturb_on_outlined,
                    title: l10n.faresMotorcycleTitle,
                    message: l10n.vehicleTypeMotorcycleNotPermitted,
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: ClaySpace.cardGap),

          if (vehicle.tag != null)
            ClayCard(
              onTap: () => context.push(
                Routes.tagDetailPath(vehicle.tag!.tagSerial),
              ),
              semanticLabel: l10n.tagsTitle,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(l10n.tagsTitle, style: textTheme.titleLarge),
                  const SizedBox(height: ClaySpace.lg),
                  DetailRow(
                    label: l10n.tagSerial,
                    value: vehicle.tag!.tagSerial,
                    monospace: true,
                  ),
                  DetailRow(
                    label: l10n.tagExpiry,
                    value: AppDates.date(
                      vehicle.tag!.expiryDate,
                      locale: localeTag(context),
                    ),
                  ),
                ],
              ),
            )
          else
            ClayBanner(
              icon: Icons.sensors_off_rounded,
              title: l10n.tagNoTagFitted,
              message: l10n.tagNoTagFittedBody,
            ),
          const SizedBox(height: ClaySpace.cardGap),

          Row(
            children: [
              Expanded(
                child: Text(l10n.vehicleTrips, style: textTheme.titleLarge),
              ),
              ClayButton(
                label: l10n.actionViewAll,
                variant: ClayButtonVariant.ghost,
                padding: const EdgeInsets.symmetric(
                  horizontal: ClaySpace.md,
                  vertical: ClaySpace.sm,
                ),
                onPressed: () => context.push(Routes.tripsPath(vehicle.id)),
              ),
            ],
          ),
          const SizedBox(height: ClaySpace.md),
          trips.when(
            loading: () => const ClaySkeletonCard(),
            error: (error, _) => ClayBanner(
              icon: Icons.cloud_off_rounded,
              title: describeError(error, l10n),
              tone: ClayTone.danger,
            ),
            data: (page) => page.items.isEmpty
                ? ClayEmptyState(
                    icon: Icons.route_rounded,
                    title: l10n.tripsEmptyTitle,
                    message: l10n.tripsEmptyBody,
                  )
                : Column(
                    children: [
                      for (final trip in page.items.take(3))
                        Padding(
                          padding: const EdgeInsets.only(
                            bottom: ClaySpace.cardGap,
                          ),
                          child: TripCard(trip: trip),
                        ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}
