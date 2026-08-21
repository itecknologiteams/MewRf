import 'package:flutter/material.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/tag.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// The authoritative tag badge.
///
/// Reads the server's `is_valid` — assigned to a vehicle AND active AND not expired
/// — rather than recomputing it from [TagStatus] and the expiry date. Two reasons:
/// the server owns "today" (a phone with a wrong clock would otherwise disagree with
/// the barrier), and `is_valid` also covers the assigned-to-a-vehicle condition,
/// which a status check alone would miss.
///
/// A tag can be `status == active` and still not valid — an active tag whose expiry
/// has passed, or one detached from its vehicle — so showing the status alone would
/// tell a driver they are fine when the gate will refuse them.
class TagStatusBadge extends StatelessWidget {
  const TagStatusBadge({required this.tag, this.dense = false, super.key});

  final Tag? tag;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final tag = this.tag;

    if (tag == null) {
      return ClayPill(
        label: l10n.tagNoTagFitted,
        icon: Icons.help_outline_rounded,
        dense: dense,
      );
    }

    if (tag.isValid) {
      return ClayPill(
        label: tag.status.label(l10n),
        tone: ClayTone.success,
        icon: Icons.check_circle_outline_rounded,
        dense: dense,
      );
    }

    // Not valid. Say WHICH problem — "not usable" alone sends someone to a booth
    // without knowing whether they need a new tag or an unblock.
    final (ClayTone tone, IconData icon, String label) = switch (tag.status) {
      TagStatus.expired => (
        ClayTone.danger,
        Icons.event_busy_rounded,
        l10n.tagStatusExpired,
      ),
      TagStatus.suspended => (
        ClayTone.warning,
        Icons.pause_circle_outline_rounded,
        l10n.tagStatusSuspended,
      ),
      TagStatus.deactivated => (
        ClayTone.danger,
        Icons.cancel_outlined,
        l10n.tagStatusDeactivated,
      ),
      // Active but not valid: the expiry date has passed even though nobody has
      // flipped the status column yet, or the tag is unassigned.
      TagStatus.active || TagStatus.unknown => (
        ClayTone.danger,
        Icons.error_outline_rounded,
        l10n.tagNotUsable,
      ),
    };

    return ClayPill(label: label, tone: tone, icon: icon, dense: dense);
  }
}

/// The "expires in N days" warning, for a tag inside its warning window.
///
/// Renders nothing when the tag is not expiring soon, so a caller can drop it in a
/// column unconditionally.
class TagExpiryWarning extends StatelessWidget {
  const TagExpiryWarning({required this.tag, this.dense = true, super.key});

  final Tag? tag;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final tag = this.tag;
    if (tag == null || !tag.isExpiringSoon) return const SizedBox.shrink();

    final days = tag.daysUntilExpiry ?? 0;
    return ClayPill(
      label: AppL10n.of(context).tagExpiringSoon(days),
      tone: ClayTone.warning,
      icon: Icons.schedule_rounded,
      dense: dense,
    );
  }
}

/// The fare class, as the notification words it.
class FareClassPill extends StatelessWidget {
  const FareClassPill({
    required this.vehicleType,
    this.dense = true,
    super.key,
  });

  final VehicleType vehicleType;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    return ClayPill(
      label: vehicleType.label(l10n),
      // A motorcycle is a valid registration class but is not allowed on the
      // expressway, so it is flagged rather than shown as ordinary.
      tone: vehicleType == VehicleType.motorcycle
          ? ClayTone.warning
          : ClayTone.primary,
      icon: switch (vehicleType) {
        VehicleType.car => Icons.directions_car_rounded,
        VehicleType.wagon => Icons.airport_shuttle_rounded,
        VehicleType.coach ||
        VehicleType.largeBus => Icons.directions_bus_rounded,
        VehicleType.truck2Axle ||
        VehicleType.truck3Axle ||
        VehicleType.truck4Axle => Icons.local_shipping_rounded,
        VehicleType.motorcycle => Icons.two_wheeler_rounded,
        VehicleType.unknown => Icons.help_outline_rounded,
      },
      dense: dense,
    );
  }
}

/// A plate number.
///
/// Monospaced-ish and always LTR: a registration number is a code, and in an Urdu
/// (RTL) layout an unconstrained `Text` reverses the visual order of a mixed
/// letter/digit string like `KDE1836`.
class PlateNumber extends StatelessWidget {
  const PlateNumber(this.plate, {this.style, super.key});

  final String plate;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) {
    final resolved = style ?? Theme.of(context).textTheme.titleLarge;
    return Text(
      plate,
      style: resolved?.copyWith(letterSpacing: 0.5),
      textDirection: TextDirection.ltr,
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
    );
  }
}
