import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/data/cached.dart';
import 'package:mtag_user_app/core/data/wallet_repository.dart';
import 'package:mtag_user_app/core/models/account.dart';
import 'package:mtag_user_app/core/models/vehicle.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/features/auth/presentation/session_controller.dart';

/// Everything the dashboard, tags and vehicles screens read.
class WalletSnapshot {
  const WalletSnapshot({
    required this.vehicles,
    required this.total,
    required this.summary,
    required this.isStale,
    this.storedAt,
  });

  final List<MyVehicle> vehicles;

  /// A sum across per-vehicle wallets, carrying its own "this is a sum" semantics.
  final WalletTotal total;

  /// Null when the summary endpoint is absent AND the client-side aggregation also
  /// failed. The dashboard still renders — it has the vehicles — just without the
  /// month-to-date figure.
  final AccountSummary? summary;

  final bool isStale;
  final DateTime? storedAt;

  List<MyVehicle> get vehiclesWithTags =>
      vehicles.where((v) => v.hasTag).toList(growable: false);

  List<MyVehicle> get vehiclesWithoutTags =>
      vehicles.where((v) => !v.hasTag).toList(growable: false);

  /// Vehicles the barrier will refuse right now: below Rs. 50.
  List<MyVehicle> get blockedVehicles => vehicles
      .where((v) => v.balanceLevel == BalanceLevel.blocked)
      .toList(growable: false);

  /// Vehicles that will pass but should be topped up: below Rs. 200.
  List<MyVehicle> get lowVehicles => vehicles
      .where((v) => v.balanceLevel == BalanceLevel.low)
      .toList(growable: false);

  MyVehicle? get firstTopUpTarget {
    if (blockedVehicles.isNotEmpty) return blockedVehicles.first;
    if (lowVehicles.isNotEmpty) return lowVehicles.first;
    return vehicles.where((v) => v.accountId != null).firstOrNull;
  }
}

/// Loads the wallet, and reloads it on demand.
///
/// Kept separate from [SessionController] on purpose: the router redirects on session
/// state, so if a failed balance refresh lived there it would bounce the user to the
/// login screen. Here a failure is just an error state on one screen.
class WalletController extends AsyncNotifier<WalletSnapshot> {
  @override
  Future<WalletSnapshot> build() async {
    final user = ref.watch(currentUserProvider);
    if (user == null) {
      // Signed out. Returning empty rather than throwing keeps the dashboard from
      // flashing an error during the redirect to login.
      return WalletSnapshot(
        vehicles: const [],
        total: WalletTotal.fromVehicles(const []),
        summary: null,
        isStale: false,
      );
    }

    final wallet = ref.watch(walletRepositoryProvider);

    // Vehicles first, then the summary — the summary fallback needs the vehicle list
    // to aggregate over, so these cannot be parallel. When the server HAS
    // /accounts/my/summary/ this costs one extra sequential round trip; when it does
    // not, the alternative is fetching the vehicle list twice.
    final vehicles = await wallet.myVehicles(userId: user.id);

    Cached<AccountSummary>? summary;
    try {
      summary = await wallet.summary(userId: user.id, vehicles: vehicles.value);
    } on Object {
      // A missing month-to-date figure must not take the balances down with it.
      summary = null;
    }

    return WalletSnapshot(
      vehicles: vehicles.value,
      total: WalletTotal.fromVehicles(vehicles.value),
      summary: summary?.value,
      // Stale if EITHER read came from cache. A fresh vehicle list beside a cached
      // summary is still partly old, and the ribbon has to say so.
      isStale: !vehicles.isFresh || (summary != null && !summary.isFresh),
      storedAt: vehicles.storedAt ?? summary?.storedAt,
    );
  }

  /// Pull-to-refresh.
  ///
  /// `state = AsyncLoading` is deliberately NOT set: that would replace the screen
  /// with skeletons while the user is already looking at content, which reads as a
  /// flash of nothing. The refresh indicator is the progress signal.
  Future<void> refresh() async {
    state = await AsyncValue.guard(build);
  }

  /// Re-reads only the balances, after a confirmed top-up.
  ///
  /// The balance is re-read from the SERVER — never computed as old + amount. That is
  /// the one rule the whole top-up flow is built around.
  Future<void> refreshBalances() => refresh();
}

final walletControllerProvider =
    AsyncNotifierProvider<WalletController, WalletSnapshot>(
      WalletController.new,
    );

/// One vehicle out of the loaded wallet, by id.
final vehicleByIdProvider = Provider.family<MyVehicle?, int>((ref, id) {
  final snapshot = ref.watch(walletControllerProvider).value;
  return snapshot?.vehicles.where((v) => v.id == id).firstOrNull;
});

/// One vehicle by its tag serial — how the deep link `mtag://tag/{serial}` resolves.
final vehicleByTagSerialProvider = Provider.family<MyVehicle?, String>((
  ref,
  serial,
) {
  final snapshot = ref.watch(walletControllerProvider).value;
  return snapshot?.vehicles
      .where((v) => v.tag?.tagSerial == serial)
      .firstOrNull;
});
