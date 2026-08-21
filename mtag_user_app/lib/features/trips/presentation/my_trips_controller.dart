import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/trip.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/features/auth/presentation/session_controller.dart';

/// The Trips segment's filter. Maps onto `?status=`, filtered SERVER-side.
///
/// Server-side for the same reason the transaction filter is: narrowing one fetched page
/// locally would report "1 open trip" for a holder whose open trip is on page 3.
enum TripFilter {
  all(null),
  live(TripStatus.active),
  completed(TripStatus.completed);

  const TripFilter(this.status);

  final TripStatus? status;
}

class MyTripsState {
  const MyTripsState({
    this.trips = const [],
    this.filter = TripFilter.all,
    this.hasMore = false,
    this.isLoadingMore = false,
    this.totalCount = 0,
    this.isFromCache = false,
  });

  final List<TollTrip> trips;
  final TripFilter filter;
  final bool hasMore;
  final bool isLoadingMore;
  final int totalCount;

  /// True when these rows came off disk because the network failed. The UI says so — a
  /// stale list presented as current is how a user concludes a toll was never charged.
  final bool isFromCache;

  bool get isEmpty => trips.isEmpty;

  /// Trips still open. Surfaced separately because "you are on the expressway now" is the
  /// one thing on this screen that is about the present rather than the past.
  Iterable<TollTrip> get live => trips.where((t) => t.isLive);

  MyTripsState copyWith({
    List<TollTrip>? trips,
    TripFilter? filter,
    bool? hasMore,
    bool? isLoadingMore,
    int? totalCount,
    bool? isFromCache,
  }) => MyTripsState(
    trips: trips ?? this.trips,
    filter: filter ?? this.filter,
    hasMore: hasMore ?? this.hasMore,
    isLoadingMore: isLoadingMore ?? this.isLoadingMore,
    totalCount: totalCount ?? this.totalCount,
    isFromCache: isFromCache ?? this.isFromCache,
  );
}

/// Trip history across every vehicle the holder owns.
///
/// Backed by `GET /tolls/trips/my/`, which is one ordered, paginated query. The older
/// per-vehicle provider ([tripsControllerProvider]) still exists and is still correct for
/// the vehicle-detail screen; it is simply the wrong shape for an account-wide list, where
/// merging N paginated streams on the client cannot produce a correct ordering.
class MyTripsController extends AsyncNotifier<MyTripsState> {
  int _page = 1;
  final List<TollTrip> _flat = [];

  @override
  Future<MyTripsState> build() async {
    _page = 1;
    _flat.clear();
    return _fetchFirstPage(TripFilter.all);
  }

  int? get _userId {
    final session = ref.read(sessionControllerProvider).value;
    return session is SessionSignedIn ? session.user.id : null;
  }

  Future<MyTripsState> _fetchFirstPage(TripFilter filter) async {
    final repo = ref.read(tollRepositoryProvider);
    final userId = _userId;

    try {
      final page = await repo.myTrips(
        status: filter.status,
        cacheForUserId: filter == TripFilter.all ? userId : null,
      );
      _page = 1;
      _flat
        ..clear()
        ..addAll(page.items);
      return MyTripsState(
        trips: List.unmodifiable(_flat),
        filter: filter,
        hasMore: page.meta.hasMore,
        totalCount: page.meta.count,
      );
    } on Object {
      // Fall back to the cached first page rather than an error screen — but only for the
      // unfiltered view, because the cache holds the unfiltered list and showing it under
      // a "Live" chip would be a lie about what the user asked for.
      if (filter == TripFilter.all && userId != null) {
        final cached = await repo.cachedMyFirstTripPage(userId);
        if (cached != null && cached.value.isNotEmpty) {
          _page = 1;
          _flat
            ..clear()
            ..addAll(cached.value);
          return MyTripsState(
            trips: List.unmodifiable(_flat),
            filter: filter,
            totalCount: cached.value.length,
            isFromCache: true,
          );
        }
      }
      rethrow;
    }
  }

  Future<void> setFilter(TripFilter filter) async {
    final current = state.value;
    if (current != null && current.filter == filter) return;
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _fetchFirstPage(filter));
  }

  Future<void> loadMore() async {
    final current = state.value;
    if (current == null ||
        !current.hasMore ||
        current.isLoadingMore ||
        // Paging a cached list would request page 2 from a server that just failed, and
        // append it to rows of unknown age.
        current.isFromCache) {
      return;
    }

    state = AsyncValue.data(current.copyWith(isLoadingMore: true));
    try {
      final next = await ref
          .read(tollRepositoryProvider)
          .myTrips(page: _page + 1, status: current.filter.status);
      _page++;
      _flat.addAll(next.items);
      state = AsyncValue.data(
        current.copyWith(
          trips: List.unmodifiable(_flat),
          hasMore: next.meta.hasMore,
          totalCount: next.meta.count,
          isLoadingMore: false,
        ),
      );
    } on Object {
      // Page number is NOT advanced on failure, so a retry re-requests the same page
      // instead of skipping it and leaving a hole in the history.
      state = AsyncValue.data(current.copyWith(isLoadingMore: false));
    }
  }

  Future<void> refresh() async {
    final filter = state.value?.filter ?? TripFilter.all;
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _fetchFirstPage(filter));
  }
}

final myTripsControllerProvider =
    AsyncNotifierProvider<MyTripsController, MyTripsState>(
      MyTripsController.new,
    );
