import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/toll.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/features/dashboard/presentation/wallet_controller.dart';

class FaresState {
  const FaresState({
    required this.plazas,
    required this.matrix,
    this.fromPlazaId,
    this.toPlazaId,
    this.vehicleType = VehicleType.car,
    this.isStale = false,
  });

  final List<Plaza> plazas;
  final FareMatrix matrix;

  /// Plaza ROW ids, because that is what `FareMatrix.from_plaza`/`to_plaza` hold — not
  /// the operator-facing `plaza_id`.
  final int? fromPlazaId;
  final int? toPlazaId;

  final VehicleType vehicleType;
  final bool isStale;

  Plaza? get fromPlaza => plazas.where((p) => p.id == fromPlazaId).firstOrNull;

  Plaza? get toPlaza => plazas.where((p) => p.id == toPlazaId).firstOrNull;

  /// The fare for the CURRENT direction only.
  ///
  /// A→B and B→A are separate rows in `fare_matrix` and the server writes both, so they
  /// can legitimately differ. Nothing here falls back to the reverse direction when a
  /// row is missing — quoting the reverse fare would be quoting a price the driver will
  /// not be charged.
  Fare? get fare {
    final from = fromPlazaId;
    final to = toPlazaId;
    if (from == null || to == null) return null;
    return matrix.lookup(
      fromPlazaId: from,
      toPlazaId: to,
      vehicleType: vehicleType,
    );
  }

  bool get hasSelection => fromPlazaId != null && toPlazaId != null;

  FaresState copyWith({
    int? fromPlazaId,
    int? toPlazaId,
    VehicleType? vehicleType,
  }) => FaresState(
    plazas: plazas,
    matrix: matrix,
    fromPlazaId: fromPlazaId ?? this.fromPlazaId,
    toPlazaId: toPlazaId ?? this.toPlazaId,
    vehicleType: vehicleType ?? this.vehicleType,
    isStale: isStale,
  );
}

class FaresController extends AsyncNotifier<FaresState> {
  @override
  Future<FaresState> build() async {
    final repository = ref.watch(tollRepositoryProvider);
    final plazas = await repository.plazas();
    final matrix = await repository.fareMatrix();

    // Auto-select the user's own fare class. It is the answer to the question they
    // actually have — "what will this trip cost MY car" — and getting it wrong by
    // defaulting to `car` for a truck owner understates the fare by up to 3x.
    final wallet = ref.watch(walletControllerProvider).value;
    final ownType = wallet?.vehicles.firstOrNull?.vehicleType;

    final active = plazas.value.where((p) => p.isActive).toList(growable: false)
      ..sort((a, b) => a.plazaId.compareTo(b.plazaId));

    return FaresState(
      plazas: active,
      matrix: matrix.value,
      vehicleType: (ownType == null || ownType == VehicleType.unknown)
          ? VehicleType.car
          : ownType,
      isStale: !plazas.isFresh || !matrix.isFresh,
    );
  }

  void setFrom(int plazaId) => _update((s) => s.copyWith(fromPlazaId: plazaId));

  void setTo(int plazaId) => _update((s) => s.copyWith(toPlazaId: plazaId));

  void setVehicleType(VehicleType type) =>
      _update((s) => s.copyWith(vehicleType: type));

  /// Swaps the direction.
  ///
  /// A real action rather than a cosmetic one: it looks up a DIFFERENT row, and the fare
  /// can change. That is why the UI makes direction explicit instead of presenting one
  /// price "between" two plazas.
  void swap() => _update(
    (s) => FaresState(
      plazas: s.plazas,
      matrix: s.matrix,
      fromPlazaId: s.toPlazaId,
      toPlazaId: s.fromPlazaId,
      vehicleType: s.vehicleType,
      isStale: s.isStale,
    ),
  );

  void _update(FaresState Function(FaresState state) transform) {
    final current = state.value;
    if (current == null) return;
    state = AsyncValue.data(transform(current));
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(build);
  }
}

final faresControllerProvider =
    AsyncNotifierProvider<FaresController, FaresState>(FaresController.new);
