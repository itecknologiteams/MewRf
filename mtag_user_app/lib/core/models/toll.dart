import 'package:decimal/decimal.dart';
import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/utils/money.dart';

part 'toll.freezed.dart';

/// A plaza, from `PlazaSerializer` (`GET /tolls/plazas/`).
///
/// **Three different numbers, and they are not interchangeable:**
///
///   * [id] — the database row id. This is what `FareMatrix.from_plaza` /
///     `to_plaza` hold, so it is the key the fare lookup joins on.
///   * [plazaId] — the operator-assigned number (1, 2, 101–107). What humans and
///     booth configs use. NOT the row id.
///   * [displayId] — [plazaId] zero-padded to three digits (`001`). Display only.
///
/// A backend bug already came from confusing these once: an activation endpoint
/// validated `booth_id` against a 1..7 range, which rejected seven of the nine real
/// plazas. The app keeps them separate at the type boundary for the same reason.
@freezed
abstract class Plaza with _$Plaza {
  const factory Plaza({
    required int id,
    required int plazaId,
    required String name,
    required bool isActive,
    double? latitude,
    double? longitude,
    @Default(<int>[]) List<int> laneNumbers,
  }) = _Plaza;

  factory Plaza.fromApi(Map<String, dynamic> json) => Plaza(
    id: (json['id'] as num).toInt(),
    plazaId: (json['plaza_id'] as num?)?.toInt() ?? 0,
    name: json['name']?.toString() ?? '',
    isActive: json['is_active'] != false,
    // Coordinates are DecimalFields and arrive as strings; they feed a map
    // pin, where double precision is entirely adequate.
    latitude: double.tryParse(json['latitude']?.toString() ?? ''),
    longitude: double.tryParse(json['longitude']?.toString() ?? ''),
    laneNumbers:
        (json['lanes'] as List?)
            ?.whereType<Map<String, dynamic>>()
            .map((lane) => (lane['lane_number'] as num?)?.toInt() ?? 0)
            .toList(growable: false) ??
        const [],
  );
}

extension PlazaX on Plaza {
  /// `plaza_id` as the operator writes it: 1 -> `001`.
  ///
  /// `PlazaSerializer` does not expose the server's `display_id` property (only
  /// `FareSerializer` does), so it is formatted here — same rule, 3-digit
  /// zero-pad, matching `plaza_registry.format_plaza_id`.
  String get displayId => plazaId.toString().padLeft(3, '0');
}

/// A billing category, from `VehicleCategorySerializer`.
///
/// [code] mirrors `Vehicle.vehicle_type`, which is what makes a vehicle joinable
/// onto the fare matrix.
@freezed
abstract class VehicleCategory with _$VehicleCategory {
  const factory VehicleCategory({
    required int id,
    required int categoryIndex,
    required String code,
    required String name,
    required bool isActive,
    @Default('') String description,
  }) = _VehicleCategory;
  // freezed needs this the moment the class declares a member of its own —
  // `vehicleType` below. Without it the generated mixin has nothing to attach to.
  const VehicleCategory._();

  factory VehicleCategory.fromApi(Map<String, dynamic> json) => VehicleCategory(
    id: (json['id'] as num).toInt(),
    categoryIndex: (json['category_index'] as num?)?.toInt() ?? 0,
    code: json['code']?.toString() ?? '',
    name: json['name']?.toString() ?? '',
    isActive: json['is_active'] != false,
    description: json['description']?.toString() ?? '',
  );

  VehicleType get vehicleType => VehicleType.parse(code);
}

/// One fare-matrix row, from `FareSerializer` (`GET /tolls/rates/`).
///
/// **Fares are directional.** A→B and B→A are separate rows and the server's
/// `load_fares` writes both, so they can legitimately differ. Nothing in this app
/// may assume symmetry — the Fares screen has an explicit swap button rather than a
/// single "between these two plazas" reading.
@freezed
abstract class Fare with _$Fare {
  const factory Fare({
    required int id,

    /// Plaza ROW ids, matching [Plaza.id] — not `plaza_id`.
    required int fromPlazaId,
    required int toPlazaId,

    /// `FareSerializer.category` is the integer `category_index`, not a row id.
    required int categoryIndex,
    required String categoryCode,
    required Decimal fare,
    @Default('') String fromPlazaName,
    @Default('') String toPlazaName,
    @Default('') String fromPlazaDisplayId,
    @Default('') String toPlazaDisplayId,
    @Default('') String categoryName,
  }) = _Fare;
  const Fare._();

  factory Fare.fromApi(Map<String, dynamic> json) => Fare(
    id: (json['id'] as num).toInt(),
    fromPlazaId: (json['from_plaza'] as num?)?.toInt() ?? 0,
    toPlazaId: (json['to_plaza'] as num?)?.toInt() ?? 0,
    categoryIndex: (json['category'] as num?)?.toInt() ?? 0,
    categoryCode: json['category_code']?.toString() ?? '',
    fare: Money.parseOrZero(json['fare']),
    fromPlazaName: json['from_plaza_name']?.toString() ?? '',
    toPlazaName: json['to_plaza_name']?.toString() ?? '',
    fromPlazaDisplayId: json['from_plaza_display_id']?.toString() ?? '',
    toPlazaDisplayId: json['to_plaza_display_id']?.toString() ?? '',
    categoryName: json['category_name']?.toString() ?? '',
  );

  VehicleType get vehicleType => VehicleType.parse(categoryCode);
}

/// The whole fare matrix, indexed for lookup.
///
/// `/tolls/rates/` returns every row — 9 plazas both directions across 8 categories
/// is a few hundred — so it is fetched once and indexed rather than filtered on
/// every keystroke of the plaza pickers.
class FareMatrix {
  FareMatrix(this.fares)
    : _byRoute = {
        for (final fare in fares)
          _key(fare.fromPlazaId, fare.toPlazaId, fare.categoryCode): fare,
      };

  final List<Fare> fares;
  final Map<String, Fare> _byRoute;

  static String _key(int from, int to, String code) => '$from>$to:$code';

  /// The fare for one direction and one fare class. Null when the operator has not
  /// loaded that combination.
  ///
  /// Joined on [VehicleType], because `category_code` mirrors
  /// `Vehicle.vehicle_type` — that is the whole point of the code column existing
  /// alongside the numeric index.
  Fare? lookup({
    required int fromPlazaId,
    required int toPlazaId,
    required VehicleType vehicleType,
  }) => _byRoute[_key(fromPlazaId, toPlazaId, vehicleType.value)];

  /// Fare classes the operator has actually loaded rates for.
  Set<VehicleType> get availableTypes => fares
      .map((f) => f.vehicleType)
      .where((t) => t != VehicleType.unknown)
      .toSet();

  bool get isEmpty => fares.isEmpty;
}
