import 'package:decimal/decimal.dart';
import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/utils/app_dates.dart';
import 'package:mtag_user_app/core/utils/money.dart';

part 'trip.freezed.dart';

/// One row of `GET /tolls/trips/{vehicle_id}/` — `TollTripSerializer`.
///
/// The endpoint is keyed by **vehicle** id, not account id.
///
/// An `active` trip is a vehicle that has entered and not yet exited: `exitPlazaName`,
/// `exitTime`, `chargeAmount` and `durationMinutes` are all null, which is a valid
/// state and not missing data. It renders as a live card.
@freezed
abstract class TollTrip with _$TollTrip {
  const factory TollTrip({
    required int id,
    required String plateNumber,
    required String entryPlazaName,
    required TripStatus status,
    DateTime? entryTime,
    String? exitPlazaName,
    DateTime? exitTime,
    Decimal? chargeAmount,
    Decimal? balanceBefore,
    Decimal? balanceAfter,

    /// The server computes this as a fractional double, not an int.
    double? durationMinutes,
  }) = _TollTrip;

  factory TollTrip.fromApi(Map<String, dynamic> json) => TollTrip(
    id: (json['id'] as num).toInt(),
    plateNumber: json['plate_number']?.toString() ?? '',
    entryPlazaName: json['entry_plaza_name']?.toString() ?? '',
    status: TripStatus.parse(json['status']),
    entryTime: AppDates.tryParseUtc(json['entry_time']),
    exitPlazaName: json['exit_plaza_name']?.toString(),
    exitTime: AppDates.tryParseUtc(json['exit_time']),
    chargeAmount: Money.tryParse(json['charge_amount']),
    balanceBefore: Money.tryParse(json['balance_before']),
    balanceAfter: Money.tryParse(json['balance_after']),
    durationMinutes: (json['duration_minutes'] as num?)?.toDouble(),
  );
}

extension TollTripX on TollTrip {
  /// On the expressway right now.
  bool get isLive => status == TripStatus.active;

  /// How long the vehicle has been inside, for a live trip.
  ///
  /// Computed against the device clock, which is the honest thing to do — the
  /// server sends no running duration for an open trip — and only ever shown with
  /// "so far" attached so it does not read as a settled figure.
  Duration? get elapsedSoFar {
    final entry = entryTime;
    if (!isLive || entry == null) return null;
    final delta = DateTime.now().toUtc().difference(entry);
    return delta.isNegative ? Duration.zero : delta;
  }
}
