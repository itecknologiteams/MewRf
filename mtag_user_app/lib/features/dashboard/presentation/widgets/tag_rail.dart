import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:mtag_user_app/core/models/tag.dart';
import 'package:mtag_user_app/core/models/vehicle.dart';
import 'package:mtag_user_app/core/router/app_router.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/shared/money_text.dart';
import 'package:mtag_user_app/features/shared/tag_status_badge.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Horizontally scrolling tag cards — one per vehicle, plate, balance and status.
///
/// This rail is what makes the hero total honest. The total above it is a sum that
/// cannot be spent as one; here each wallet appears on its own, with its own
/// urgency, so "Rs. 4,250 across 3 tags" resolves into the three real numbers.
///
/// Vehicles with no tag are INCLUDED, as an explicit "No tag fitted" card. Dropping
/// them would make a vehicle silently disappear mid-reissue, which is exactly when its
/// owner is looking for it.
class TagRail extends StatelessWidget {
  const TagRail({required this.vehicles, super.key});

  final List<MyVehicle> vehicles;

  /// Fixed width so the next card peeks in from the edge — the standard cue that a
  /// row scrolls, and one that costs nothing to read.
  static const _cardWidth = 224.0;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 176,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        // Reaches the screen edge on purpose; the parent's gutter is re-applied here
        // so the first card lines up with the cards above it while the rail itself can
        // still bleed off-screen.
        padding: EdgeInsets.zero,
        clipBehavior: Clip.none,
        itemCount: vehicles.length,
        separatorBuilder: (_, _) => const SizedBox(width: ClaySpace.md),
        itemBuilder: (context, index) {
          final vehicle = vehicles[index];
          return SizedBox(
            width: _cardWidth,
            child: _TagCard(vehicle: vehicle),
          );
        },
      ),
    );
  }
}

class _TagCard extends StatelessWidget {
  const _TagCard({required this.vehicle});

  final MyVehicle vehicle;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final textTheme = Theme.of(context).textTheme;
    final serial = vehicle.tag?.tagSerial;

    return ClayCard(
      padding: const EdgeInsets.all(ClaySpace.lg),
      semanticLabel: vehicle.plateNumber,
      onTap: serial == null
          // Without a tag there is no tag-detail screen to open; the vehicle screen is
          // where the reissue story lives.
          ? () => context.push(Routes.vehicleDetailPath(vehicle.id))
          : () => context.push(Routes.tagDetailPath(serial)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          PlateNumber(vehicle.plateNumber, style: textTheme.titleMedium),
          const SizedBox(height: ClaySpace.sm),
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: TagStatusBadge(tag: vehicle.tag, dense: true),
          ),
          const Spacer(),
          Text(l10n.vehicleBalance, style: textTheme.labelSmall),
          const SizedBox(height: ClaySpace.xs),
          BalanceFigure(
            amount: vehicle.balance,
            level: vehicle.balanceLevel,
            style: textTheme.displaySmall,
          ),
          if (vehicle.tag?.isExpiringSoon ?? false) ...[
            const SizedBox(height: ClaySpace.sm),
            TagExpiryWarning(tag: vehicle.tag),
          ],
        ],
      ),
    );
  }
}
