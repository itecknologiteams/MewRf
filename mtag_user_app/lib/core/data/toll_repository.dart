import 'package:mtag_user_app/core/cache/cache_database.dart';
import 'package:mtag_user_app/core/data/cached.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/toll.dart';
import 'package:mtag_user_app/core/models/trip.dart';
import 'package:mtag_user_app/core/network/api_client.dart';
import 'package:mtag_user_app/core/network/api_envelope.dart';
import 'package:mtag_user_app/core/utils/money.dart';

/// Trips, plazas and fares.
class TollRepository {
  TollRepository({required ApiClient client, required CacheDatabase cache})
    : _client = client,
      _cache = cache;

  final ApiClient _client;
  final CacheDatabase _cache;

  /// Trips for a vehicle. **Keyed by VEHICLE id**, not account id.
  Future<PagedEnvelope<TollTrip>> trips({
    required int vehicleId,
    int page = 1,
  }) async {
    final result = await _client.getPaged<TollTrip>(
      'tolls/trips/$vehicleId/',
      parseItem: TollTrip.fromApi,
      page: page,
    );
    if (page == 1) {
      await _cache.write(
        CacheKeys.tripsFirstPage(vehicleId),
        result.items.map(_encodeTrip).toList(),
      );
    }
    return result;
  }

  /// Every trip across every vehicle the holder owns — `GET /tolls/trips/my/`.
  ///
  /// A single server-side query rather than one request per vehicle. Fanning out on the
  /// client and stitching the results is not merely slower, it is wrong: page 1 of two
  /// vehicles is not the first page of their union, so a merged list either repeats rows or
  /// drops them as the user scrolls.
  ///
  /// [status] maps to `?status=` and the server REFUSES an unknown value, so only real
  /// [TripStatus] values are sent — never `TripStatus.unknown`, which exists to absorb a
  /// status this build has not heard of and would come back as a 400.
  Future<PagedEnvelope<TollTrip>> myTrips({
    int page = 1,
    TripStatus? status,
    int? cacheForUserId,
  }) async {
    final result = await _client.getPaged<TollTrip>(
      'tolls/trips/my/',
      parseItem: TollTrip.fromApi,
      page: page,
      query: {
        if (status != null && status != TripStatus.unknown)
          'status': status.value,
      },
    );
    // Only the unfiltered first page is cached. Caching a filtered page under the same key
    // would let "active only" results resurface later as the whole history.
    if (page == 1 && status == null && cacheForUserId != null) {
      await _cache.write(
        CacheKeys.myTripsFirstPage(cacheForUserId),
        result.items.map(_encodeTrip).toList(),
      );
    }
    return result;
  }

  Future<Cached<List<TollTrip>>?> cachedMyFirstTripPage(int userId) =>
      readCacheOnly<List<TollTrip>>(
        cache: _cache,
        key: CacheKeys.myTripsFirstPage(userId),
        decode: _decodeTrips,
      );

  Future<Cached<List<TollTrip>>?> cachedFirstTripPage(int vehicleId) =>
      readCacheOnly<List<TollTrip>>(
        cache: _cache,
        key: CacheKeys.tripsFirstPage(vehicleId),
        decode: _decodeTrips,
      );

  /// The plaza list. Cached hard: it changes when the operator builds a new
  /// interchange, which is not often, and the Fares screen is unusable without it.
  Future<Cached<List<Plaza>>> plazas() => fetchWithCache<List<Plaza>>(
    cache: _cache,
    key: CacheKeys.plazas,
    fetch: () => _client.get<List<Plaza>>(
      'tolls/plazas/',
      parse: (data) => (data as List)
          .whereType<Map<String, dynamic>>()
          .map(Plaza.fromApi)
          .toList(growable: false),
    ),
    encode: (plazas) => plazas.map(_encodePlaza).toList(),
    decode: _decodePlazas,
  );

  /// The whole fare matrix, in one call.
  ///
  /// Not paginated server-side and not filterable, so it arrives entire — a few
  /// hundred rows for 9 plazas × 2 directions × 8 categories. Fetched once and
  /// indexed by [FareMatrix]; re-fetching per lookup would be a request per
  /// keystroke for data that changes when a rate is revised.
  Future<Cached<FareMatrix>> fareMatrix() => fetchWithCache<FareMatrix>(
    cache: _cache,
    key: CacheKeys.fares,
    fetch: () async {
      final fares = await _client.get<List<Fare>>(
        'tolls/rates/',
        parse: (data) => (data as List)
            .whereType<Map<String, dynamic>>()
            .map(Fare.fromApi)
            .toList(growable: false),
      );
      return FareMatrix(fares);
    },
    encode: (matrix) => matrix.fares.map(_encodeFare).toList(),
    decode: (json) => FareMatrix(_decodeFares(json)),
  );

  Future<Cached<List<VehicleCategory>>> categories() =>
      fetchWithCache<List<VehicleCategory>>(
        cache: _cache,
        key: CacheKeys.categories,
        fetch: () => _client.get<List<VehicleCategory>>(
          'tolls/vehicle-categories/',
          parse: (data) => (data as List)
              .whereType<Map<String, dynamic>>()
              .map(VehicleCategory.fromApi)
              .toList(growable: false),
        ),
        encode: (categories) => categories.map(_encodeCategory).toList(),
        decode: (json) => (json as List)
            .whereType<Map<String, dynamic>>()
            .map(VehicleCategory.fromApi)
            .toList(growable: false),
      );

  // ── Cache encoding, in the server's wire shape ─────────────────────────────

  static List<TollTrip> _decodeTrips(dynamic json) => (json as List)
      .whereType<Map<String, dynamic>>()
      .map(TollTrip.fromApi)
      .toList(growable: false);

  static List<Plaza> _decodePlazas(dynamic json) => (json as List)
      .whereType<Map<String, dynamic>>()
      .map(Plaza.fromApi)
      .toList(growable: false);

  static List<Fare> _decodeFares(dynamic json) => (json as List)
      .whereType<Map<String, dynamic>>()
      .map(Fare.fromApi)
      .toList(growable: false);

  static Map<String, Object?> _encodeTrip(TollTrip trip) => {
    'id': trip.id,
    'plate_number': trip.plateNumber,
    'entry_plaza_name': trip.entryPlazaName,
    'exit_plaza_name': trip.exitPlazaName,
    'entry_time': trip.entryTime?.toIso8601String(),
    'exit_time': trip.exitTime?.toIso8601String(),
    'charge_amount': trip.chargeAmount == null
        ? null
        : Money.toApiString(trip.chargeAmount!),
    'balance_before': trip.balanceBefore == null
        ? null
        : Money.toApiString(trip.balanceBefore!),
    'balance_after': trip.balanceAfter == null
        ? null
        : Money.toApiString(trip.balanceAfter!),
    'status': trip.status.value,
    'duration_minutes': trip.durationMinutes,
  };

  static Map<String, Object?> _encodePlaza(Plaza plaza) => {
    'id': plaza.id,
    'plaza_id': plaza.plazaId,
    'name': plaza.name,
    'latitude': plaza.latitude,
    'longitude': plaza.longitude,
    'is_active': plaza.isActive,
    'lanes': plaza.laneNumbers
        .map((number) => {'lane_number': number, 'is_active': true})
        .toList(),
  };

  static Map<String, Object?> _encodeFare(Fare fare) => {
    'id': fare.id,
    'from_plaza': fare.fromPlazaId,
    'to_plaza': fare.toPlazaId,
    'from_plaza_name': fare.fromPlazaName,
    'to_plaza_name': fare.toPlazaName,
    'from_plaza_display_id': fare.fromPlazaDisplayId,
    'to_plaza_display_id': fare.toPlazaDisplayId,
    'category': fare.categoryIndex,
    'category_code': fare.categoryCode,
    'category_name': fare.categoryName,
    'fare': Money.toApiString(fare.fare),
  };

  static Map<String, Object?> _encodeCategory(VehicleCategory category) => {
    'id': category.id,
    'category_index': category.categoryIndex,
    'code': category.code,
    'name': category.name,
    'description': category.description,
    'is_active': category.isActive,
  };
}
