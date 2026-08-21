import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/models/trip.dart';
import 'package:mtag_user_app/core/network/api_envelope.dart';
import 'package:mtag_user_app/core/providers.dart';

/// The first page of a vehicle's trips.
///
/// Keyed by **vehicle** id — `/tolls/trips/{vehicle_id}/` — not account id. The two are
/// both ints and the app carries both, so the parameter name is doing real work here.
final vehicleTripsProvider =
    FutureProvider.family<PagedEnvelope<TollTrip>, int>((ref, vehicleId) {
      return ref.watch(tollRepositoryProvider).trips(vehicleId: vehicleId);
    });

/// Paginated trip history for one vehicle.
///
/// The vehicle id arrives through the CONSTRUCTOR, not through `build()`. That is how
/// Riverpod 3 wires a class-based family: the provider's create function is
/// `TripsController Function(int)`, so `TripsController.new` receives the argument and
/// `build()` stays parameterless.
class TripsController extends AsyncNotifier<PagedEnvelope<TollTrip>> {
  TripsController(this.vehicleId);

  final int vehicleId;

  int _page = 1;
  PagedEnvelope<TollTrip>? _accumulated;

  @override
  Future<PagedEnvelope<TollTrip>> build() async {
    _page = 1;
    final first = await ref
        .watch(tollRepositoryProvider)
        .trips(vehicleId: vehicleId);
    _accumulated = first;
    return first;
  }

  Future<void> loadMore() async {
    final current = _accumulated;
    if (current == null || !current.meta.hasMore) return;

    _page++;
    try {
      final next = await ref
          .read(tollRepositoryProvider)
          .trips(vehicleId: vehicleId, page: _page);
      _accumulated = current.append(next);
      state = AsyncValue.data(_accumulated!);
    } on Object {
      // Roll back so a retry re-requests the same page rather than skipping it and
      // leaving a gap in the history.
      _page--;
    }
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(build);
  }
}

final tripsControllerProvider = AsyncNotifierProvider.autoDispose
    .family<TripsController, PagedEnvelope<TollTrip>, int>(TripsController.new);
