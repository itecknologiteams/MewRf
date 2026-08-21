import 'package:decimal/decimal.dart';
import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:mtag_user_app/core/env/app_env.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/tag.dart';
import 'package:mtag_user_app/core/utils/app_dates.dart';
import 'package:mtag_user_app/core/utils/money.dart';

part 'vehicle.freezed.dart';

/// How urgent a balance is.
///
/// Derived once, here, so the dashboard banner, the tag list and the tag detail
/// screen cannot disagree about whether Rs. 49 is a problem.
enum BalanceLevel {
  /// Below Rs. 50 — the barrier will NOT open. A hard stop, not a nudge.
  blocked,

  /// Below Rs. 200 — will open, but top up soon.
  low,

  ok,

  /// No account, or a balance the server did not send. Never rendered as Rs. 0.
  unknown,
}

/// One row of `GET /vehicles/my/` — the app's bootstrap shape.
///
/// A vehicle, its tag, and its wallet in one object.
///
/// **The wallet belongs to the vehicle, not the user.** `Account` is a OneToOne on
/// `Vehicle`, so a holder with three vehicles has three independent balances and
/// cannot spend one at another's plaza. Any "total" the app shows is a client-side
/// sum and is labelled as one.
@freezed
abstract class MyVehicle with _$MyVehicle {
  const factory MyVehicle({
    required int id,
    required String plateNumber,
    required VehicleType vehicleType,
    required VehicleStatus status,
    DateTime? registeredAt,
    Tag? tag,
    int? accountId,

    /// Null means "not known" — no account row, or a field the server omitted.
    /// Distinct from Rs. 0, and the UI must keep them distinct: a driver told
    /// their balance is zero will top up; one shown a dash will refresh.
    Decimal? balance,
    DateTime? balanceUpdatedAt,
  }) = _MyVehicle;

  factory MyVehicle.fromApi(Map<String, dynamic> json) {
    final rawTag = json['tag'];
    return MyVehicle(
      id: (json['id'] as num).toInt(),
      plateNumber: json['plate_number']?.toString() ?? '',
      vehicleType: VehicleType.parse(json['vehicle_type']),
      status: VehicleStatus.parse(json['status']),
      registeredAt: AppDates.tryParseUtc(json['registered_at']),
      // tag is legitimately null: a vehicle mid-reissue has no tag row. Such a
      // vehicle is shown as "No tag fitted", never dropped from the list — it is
      // exactly the state a worried holder opens the app to check.
      tag: rawTag is Map<String, dynamic> ? Tag.fromApi(rawTag) : null,
      accountId: (json['account_id'] as num?)?.toInt(),
      balance: Money.tryParse(json['balance']),
      balanceUpdatedAt: AppDates.tryParseUtc(json['balance_updated_at']),
    );
  }
}

extension MyVehicleX on MyVehicle {
  bool get hasTag => tag != null;

  BalanceLevel get balanceLevel {
    final value = balance;
    if (value == null) return BalanceLevel.unknown;
    if (value < Money.fromInt(AppEnv.minimumEntryBalance)) {
      return BalanceLevel.blocked;
    }
    if (value < Money.fromInt(AppEnv.lowBalanceWarning)) {
      return BalanceLevel.low;
    }
    return BalanceLevel.ok;
  }

  /// Whether this vehicle can actually pass a gate right now.
  ///
  /// Both conditions have to hold and they fail for different reasons, so the UI
  /// says which: a valid tag with Rs. 40 needs a top-up, an expired tag with
  /// Rs. 5,000 needs a booth visit.
  bool get canEnter =>
      (tag?.isValid ?? false) && balanceLevel != BalanceLevel.blocked;
}

/// `GET /vehicles/{id}/` and `GET /vehicles/plate/{plate}/` — `VehicleSerializer`.
///
/// Carries owner fields the `my/` shape does not. Kept separate rather than merged
/// because this endpoint has no `account_id` or `balance`, and a single model with
/// six nullable fields would make it impossible to tell "this endpoint does not
/// return balance" from "this vehicle has no balance".
@freezed
abstract class VehicleDetail with _$VehicleDetail {
  const factory VehicleDetail({
    required int id,
    required String plateNumber,
    required VehicleType vehicleType,
    required VehicleStatus status,
    DateTime? registeredAt,
    Tag? tag,
    int? ownerId,
    String? ownerPhone,
    String? ownerName,
  }) = _VehicleDetail;

  factory VehicleDetail.fromApi(Map<String, dynamic> json) {
    final rawTag = json['tag'];
    return VehicleDetail(
      id: (json['id'] as num).toInt(),
      plateNumber: json['plate_number']?.toString() ?? '',
      vehicleType: VehicleType.parse(json['vehicle_type']),
      status: VehicleStatus.parse(json['status']),
      registeredAt: AppDates.tryParseUtc(json['registered_at']),
      tag: rawTag is Map<String, dynamic> ? Tag.fromApi(rawTag) : null,
      ownerId: (json['owner_id'] as num?)?.toInt(),
      ownerPhone: json['owner_phone']?.toString(),
      ownerName: json['owner_name']?.toString(),
    );
  }
}
