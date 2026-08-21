import 'package:flutter/material.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/trip.dart';
import 'package:mtag_user_app/core/utils/app_dates.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/shared/money_text.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// One trip: entry plaza → exit plaza, times, duration, fare.
///
/// An `active` trip renders as a **distinct live card** rather than a completed one
/// with blank fields. It genuinely has no exit plaza, no exit time and no fare yet —
/// those are null because the vehicle is still on the expressway — and showing dashes
/// where a fare belongs reads as missing data rather than as an open journey.
class TripCard extends StatelessWidget {
  const TripCard({required this.trip, this.showPlate = false, super.key});

  final TollTrip trip;
  final bool showPlate;

  @override
  Widget build(BuildContext context) {
    if (trip.isLive) return _LiveTripCard(trip: trip, showPlate: showPlate);

    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;
    final failed = trip.status == TripStatus.failed;

    return ClayCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  AppDates.date(trip.entryTime, locale: localeTag(context)),
                  style: textTheme.labelMedium,
                ),
              ),
              if (showPlate)
                Text(
                  trip.plateNumber,
                  style: textTheme.labelMedium,
                  textDirection: TextDirection.ltr,
                ),
              if (failed) ...[
                const SizedBox(width: ClaySpace.sm),
                ClayPill(
                  label: l10n.tripStatusFailed,
                  tone: ClayTone.danger,
                  icon: Icons.error_outline_rounded,
                  dense: true,
                ),
              ],
            ],
          ),
          const SizedBox(height: ClaySpace.lg),

          _PlazaLeg(
            icon: Icons.login_rounded,
            label: l10n.tripEntry,
            plaza: trip.entryPlazaName,
            time: AppDates.time(trip.entryTime, locale: localeTag(context)),
          ),
          // The connector is a pressed groove, not a Divider — it is the one place a
          // vertical line is meaningful, so it is carved rather than drawn.
          const Padding(
            padding: EdgeInsets.only(left: 19),
            child: ClaySurface(
              style: ClayDepthStyle.pressed,
              radius: ClayRadius.pill,
              width: 3,
              height: 18,
            ),
          ),
          _PlazaLeg(
            icon: Icons.logout_rounded,
            label: l10n.tripExit,
            plaza: trip.exitPlazaName ?? l10n.unknownValue,
            time: AppDates.time(trip.exitTime, locale: localeTag(context)),
          ),

          const SizedBox(height: ClaySpace.lg),
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(l10n.tripDuration, style: textTheme.labelSmall),
                    const SizedBox(height: 2),
                    Text(
                      AppDates.duration(trip.durationMinutes),
                      style: textTheme.bodyMedium,
                      textDirection: TextDirection.ltr,
                    ),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(l10n.tripFare, style: textTheme.labelSmall),
                  const SizedBox(height: 2),
                  MoneyText(
                    trip.chargeAmount,
                    style: textTheme.titleLarge,
                    color: palette.textPrimary,
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// The live card: entered, not yet exited.
class _LiveTripCard extends StatelessWidget {
  const _LiveTripCard({required this.trip, required this.showPlate});

  final TollTrip trip;
  final bool showPlate;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;
    final elapsed = trip.elapsedSoFar;

    return ClayCard(
      // Tinted, and the only card in the app that is — a journey in progress should be
      // findable at a glance in a list of finished ones.
      color: Color.alphaBlend(
        palette.primary.withValues(alpha: 0.10),
        palette.surface,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.navigation_rounded,
                size: 18,
                color: palette.primaryOnSurface,
              ),
              const SizedBox(width: ClaySpace.sm),
              Expanded(
                child: Text(
                  l10n.tripLiveTitle,
                  style: textTheme.titleMedium?.copyWith(
                    color: palette.primaryOnSurface,
                  ),
                ),
              ),
              if (showPlate)
                Text(
                  trip.plateNumber,
                  style: textTheme.labelMedium,
                  textDirection: TextDirection.ltr,
                ),
            ],
          ),
          const SizedBox(height: ClaySpace.md),
          Text(
            l10n.tripLiveBody(
              trip.entryPlazaName,
              AppDates.time(trip.entryTime, locale: localeTag(context)),
            ),
            style: textTheme.bodyMedium,
          ),
          if (elapsed != null) ...[
            const SizedBox(height: ClaySpace.md),
            ClayPill(
              // "so far", always — the server sends no running duration for an open
              // trip, so this is computed from the device clock and must not read as a
              // settled figure.
              label: l10n.tripLiveElapsed(
                AppDates.duration(elapsed.inMinutes.toDouble()),
              ),
              tone: ClayTone.primary,
              icon: Icons.schedule_rounded,
              dense: true,
            ),
          ],
        ],
      ),
    );
  }
}

class _PlazaLeg extends StatelessWidget {
  const _PlazaLeg({
    required this.icon,
    required this.label,
    required this.plaza,
    required this.time,
  });

  final IconData icon;
  final String label;
  final String plaza;
  final String time;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ClaySurface(
          style: ClayDepthStyle.pressed,
          depth: ClayDepth.nested,
          radius: ClayRadius.pill,
          width: 38,
          height: 38,
          child: Center(
            child: Icon(icon, size: 16, color: palette.textMuted),
          ),
        ),
        const SizedBox(width: ClaySpace.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: textTheme.labelSmall),
              Text(
                plaza,
                style: textTheme.bodyMedium,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
        const SizedBox(width: ClaySpace.sm),
        Padding(
          padding: const EdgeInsets.only(top: ClaySpace.md),
          child: Text(
            time,
            style: textTheme.bodySmall,
            textDirection: TextDirection.ltr,
          ),
        ),
      ],
    );
  }
}
