import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mtag_user_app/core/models/vehicle.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/core/router/app_router.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/dashboard/presentation/wallet_controller.dart';
import 'package:mtag_user_app/features/shared/money_text.dart';
import 'package:mtag_user_app/features/shared/tag_status_badge.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

class VehiclesScreen extends ConsumerWidget {
  const VehiclesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppL10n.of(context);
    final async = ref.watch(walletControllerProvider);
    // False only after a probe has actually 404'd, so this cannot mislabel a network
    // failure as a missing endpoint.
    final endpointMissing =
        ref.watch(capabilitiesProvider).hasMyVehicles == false;

    return ClayScaffold(
      title: l10n.vehiclesTitle,
      showBack: true,
      body: async.when(
        loading: () => ListView(
          physics: const NeverScrollableScrollPhysics(),
          children: const [
            ClaySkeletonCard(height: 150),
            SizedBox(height: ClaySpace.cardGap),
            ClaySkeletonCard(height: 150),
          ],
        ),
        error: (error, _) => ClayErrorState(
          message: describeError(error, l10n),
          retryLabel: l10n.actionRetry,
          onRetry: () => ref.read(walletControllerProvider.notifier).refresh(),
        ),
        data: (snapshot) {
          if (snapshot.vehicles.isEmpty) {
            return ClayEmptyState(
              icon: Icons.no_transfer_rounded,
              // Two genuinely different situations, and conflating them would send a
              // user to a booth for a server problem: either they own nothing, or this
              // backend cannot list what they own. `GET /vehicles/` is IsOperator, so
              // without `/vehicles/my/` there is no consumer listing at all.
              title: endpointMissing
                  ? l10n.vehiclesUnavailableTitle
                  : l10n.vehiclesEmptyTitle,
              message: endpointMissing
                  ? l10n.vehiclesUnavailableBody
                  : l10n.vehiclesEmptyBody,
              tone: endpointMissing ? ClayTone.warning : ClayTone.primary,
            );
          }

          return RefreshIndicator(
            onRefresh: () =>
                ref.read(walletControllerProvider.notifier).refresh(),
            child: ListView.separated(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.only(bottom: ClaySpace.xxl),
              itemCount: snapshot.vehicles.length,
              separatorBuilder: (_, _) =>
                  const SizedBox(height: ClaySpace.cardGap),
              itemBuilder: (context, index) =>
                  _VehicleTile(vehicle: snapshot.vehicles[index]),
            ),
          );
        },
      ),
    );
  }
}

class _VehicleTile extends StatelessWidget {
  const _VehicleTile({required this.vehicle});

  final MyVehicle vehicle;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final textTheme = Theme.of(context).textTheme;

    return ClayCard(
      onTap: () => context.push(Routes.vehicleDetailPath(vehicle.id)),
      semanticLabel: vehicle.plateNumber,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: PlateNumber(vehicle.plateNumber)),
              TagStatusBadge(tag: vehicle.tag, dense: true),
            ],
          ),
          const SizedBox(height: ClaySpace.md),
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: FareClassPill(vehicleType: vehicle.vehicleType),
          ),
          const SizedBox(height: ClaySpace.lg),
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(l10n.vehicleBalance, style: textTheme.labelSmall),
                    const SizedBox(height: 2),
                    BalanceFigure(
                      amount: vehicle.balance,
                      level: vehicle.balanceLevel,
                      style: textTheme.titleLarge,
                    ),
                  ],
                ),
              ),
              ClayButton(
                label: l10n.vehicleTrips,
                variant: ClayButtonVariant.ghost,
                padding: const EdgeInsets.symmetric(
                  horizontal: ClaySpace.md,
                  vertical: ClaySpace.sm,
                ),
                onPressed: () => context.push(Routes.tripsPath(vehicle.id)),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
