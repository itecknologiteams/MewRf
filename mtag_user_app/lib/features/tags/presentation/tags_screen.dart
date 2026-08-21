import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mtag_user_app/core/models/tag.dart';
import 'package:mtag_user_app/core/models/vehicle.dart';
import 'package:mtag_user_app/core/router/app_router.dart';
import 'package:mtag_user_app/core/utils/app_dates.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/dashboard/presentation/wallet_controller.dart';
import 'package:mtag_user_app/features/shared/money_text.dart';
import 'package:mtag_user_app/features/shared/tag_status_badge.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Every tag the user holds.
///
/// A vehicle with NO tag gets an explicit "No tag fitted" row rather than being
/// dropped. That is the case a worried owner opens this screen for — a reissue in
/// progress — and a silently shorter list would read as a lost vehicle.
class TagsScreen extends ConsumerWidget {
  const TagsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final async = ref.watch(walletControllerProvider);

    return Scaffold(
      backgroundColor: palette.base,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(
                ClaySpace.gutter,
                ClaySpace.lg,
                ClaySpace.gutter,
                ClaySpace.md,
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          l10n.tagsTitle,
                          style: Theme.of(context).textTheme.headlineMedium,
                        ),
                        if (async.value != null)
                          Text(
                            l10n.tagsSubtitle(
                              async.value!.vehiclesWithTags.length,
                            ),
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                      ],
                    ),
                  ),
                  ClayIconButton(
                    icon: Icons.directions_car_rounded,
                    semanticLabel: l10n.vehiclesTitle,
                    onPressed: () => context.push(Routes.vehicles),
                  ),
                ],
              ),
            ),
            Expanded(
              child: async.when(
                loading: () => const _TagsSkeleton(),
                error: (error, _) => Padding(
                  padding: const EdgeInsets.all(ClaySpace.gutter),
                  child: ClayErrorState(
                    message: describeError(error, l10n),
                    retryLabel: l10n.actionRetry,
                    onRetry: () =>
                        ref.read(walletControllerProvider.notifier).refresh(),
                  ),
                ),
                data: (snapshot) => RefreshIndicator(
                  onRefresh: () =>
                      ref.read(walletControllerProvider.notifier).refresh(),
                  color: palette.primary,
                  backgroundColor: palette.surface,
                  child: snapshot.vehicles.isEmpty
                      ? ListView(
                          children: [
                            SizedBox(
                              height: MediaQuery.sizeOf(context).height * 0.55,
                              child: ClayEmptyState(
                                icon: Icons.sensors_off_rounded,
                                title: l10n.tagsEmptyTitle,
                                message: l10n.tagsEmptyBody,
                              ),
                            ),
                          ],
                        )
                      : ListView.separated(
                          padding: const EdgeInsets.only(
                            left: ClaySpace.gutter,
                            right: ClaySpace.gutter,
                            bottom: ClaySpace.xl,
                          ),
                          physics: const AlwaysScrollableScrollPhysics(),
                          itemCount: snapshot.vehicles.length,
                          separatorBuilder: (_, _) =>
                              const SizedBox(height: ClaySpace.cardGap),
                          itemBuilder: (context, index) =>
                              TagListTile(vehicle: snapshot.vehicles[index]),
                        ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// One tag row: serial, plate, status, expiry, balance.
class TagListTile extends StatelessWidget {
  const TagListTile({required this.vehicle, super.key});

  final MyVehicle vehicle;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;
    final tag = vehicle.tag;

    return ClayCard(
      semanticLabel: '${vehicle.plateNumber} ${tag?.tagSerial ?? ''}',
      onTap: tag == null
          ? () => context.push(Routes.vehicleDetailPath(vehicle.id))
          : () => context.push(Routes.tagDetailPath(tag.tagSerial)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    PlateNumber(vehicle.plateNumber),
                    const SizedBox(height: 2),
                    Text(
                      tag == null
                          ? l10n.tagNoTagFitted
                          : '${l10n.tagSerial} ${tag.tagSerial}',
                      style: textTheme.bodySmall,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      // A serial is a code: LTR even in an Urdu layout.
                      textDirection: TextDirection.ltr,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: ClaySpace.md),
              TagStatusBadge(tag: tag, dense: true),
            ],
          ),

          if (tag == null) ...[
            const SizedBox(height: ClaySpace.md),
            Text(l10n.tagNoTagFittedBody, style: textTheme.bodySmall),
          ],

          const SizedBox(height: ClaySpace.lg),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
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
                      style: textTheme.displaySmall,
                    ),
                  ],
                ),
              ),
              if (tag?.expiryDate != null)
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(l10n.tagExpiry, style: textTheme.labelSmall),
                    const SizedBox(height: 2),
                    Text(
                      AppDates.date(
                        tag!.expiryDate,
                        locale: localeTag(context),
                      ),
                      style: textTheme.bodyMedium?.copyWith(
                        color: tag.isExpiringSoon
                            ? palette.warningOnSurface
                            : palette.textPrimary,
                      ),
                    ),
                  ],
                ),
            ],
          ),

          if (tag?.isExpiringSoon ?? false) ...[
            const SizedBox(height: ClaySpace.md),
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: TagExpiryWarning(tag: tag, dense: false),
            ),
          ],
        ],
      ),
    );
  }
}

class _TagsSkeleton extends StatelessWidget {
  const _TagsSkeleton();

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.symmetric(horizontal: ClaySpace.gutter),
    physics: const NeverScrollableScrollPhysics(),
    children: const [
      ClaySkeletonCard(lines: 4, height: 180),
      SizedBox(height: ClaySpace.cardGap),
      ClaySkeletonCard(lines: 4, height: 180),
    ],
  );
}
