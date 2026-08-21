import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/core/data/wallet_repository.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/trip.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/dashboard/presentation/wallet_controller.dart';
import 'package:mtag_user_app/features/transactions/presentation/transactions_controller.dart';
import 'package:mtag_user_app/features/transactions/presentation/transactions_screen.dart';
import 'package:mtag_user_app/features/trips/presentation/my_trips_controller.dart';
import 'package:mtag_user_app/features/trips/presentation/widgets/trip_card.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Trips have to be REACHABLE, not merely implemented.
///
/// The screens and providers for trip history existed all along; the only route to them was
/// Home > a stat tile > Vehicles > pick a vehicle > detail > "View all" — four taps down,
/// behind a tile labelled for vehicles — and none of the five nav tabs led there. So the
/// feature was invisible in practice, and no test noticed because every test asserted on
/// widgets it had constructed directly.
///
/// These tests drive the screen the way a user does: tap the segment, expect trips.
class _Trips extends MyTripsController {
  _Trips(this._state);

  final MyTripsState _state;

  @override
  Future<MyTripsState> build() async => _state;
}

class _Txns extends TransactionsController {
  @override
  Future<TransactionsState> build() async => const TransactionsState();
}

class _Wallet extends WalletController {
  @override
  Future<WalletSnapshot> build() async => WalletSnapshot(
    vehicles: const [],
    total: WalletTotal.fromVehicles(const []),
    summary: null,
    isStale: false,
  );
}

TollTrip _trip({
  required int id,
  required String plate,
  TripStatus status = TripStatus.completed,
}) => TollTrip(
  id: id,
  plateNumber: plate,
  entryPlazaName: 'Shahfaisal Main Toll Plaza',
  status: status,
  entryTime: DateTime.utc(2026, 3, 1, 9, 30).subtract(Duration(hours: id)),
  exitPlazaName: status == TripStatus.active ? null : 'Kathor Main Toll Plaza',
  exitTime: status == TripStatus.active ? null : DateTime.utc(2026, 3, 1, 10),
  chargeAmount: status == TripStatus.active ? null : Decimal.parse('120.00'),
  durationMinutes: status == TripStatus.active ? null : 30,
);

void main() {
  setUpAll(() {
    FlutterError.onError = (details) =>
        fail('Layout error: ${details.exceptionAsString()}');
  });

  Future<void> pumpActivity(
    WidgetTester tester, {
    required MyTripsState trips,
    Size size = const Size(420, 900),
  }) async {
    tester.view
      ..physicalSize = size
      ..devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          myTripsControllerProvider.overrideWith(() => _Trips(trips)),
          transactionsControllerProvider.overrideWith(_Txns.new),
          walletControllerProvider.overrideWith(_Wallet.new),
        ],
        child: MaterialApp(
          theme: clayDarkTheme(),
          localizationsDelegates: const [
            AppL10n.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          supportedLocales: AppL10n.supportedLocales,
          home: const TransactionsScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('Activity opens on Payments and offers a Trips segment', (
    tester,
  ) async {
    await pumpActivity(tester, trips: const MyTripsState());

    // Both segments visible without scrolling, or the feature is still hidden.
    expect(find.text('Payments'), findsOneWidget);
    expect(find.text('Trips'), findsOneWidget);
    // Payments first: money is what most sessions are about.
    expect(find.byType(TripCard), findsNothing);
  });

  testWidgets('tapping Trips shows trip cards', (tester) async {
    await pumpActivity(
      tester,
      trips: MyTripsState(
        trips: [
          _trip(id: 1, plate: 'KDE1836'),
          _trip(id: 2, plate: 'KDE7777'),
        ],
        totalCount: 2,
      ),
    );

    await tester.tap(find.text('Trips'));
    await tester.pumpAndSettle();

    expect(find.byType(TripCard), findsNWidgets(2));
  });

  testWidgets('a live trip renders on the Trips segment', (tester) async {
    await pumpActivity(
      tester,
      trips: MyTripsState(
        trips: [_trip(id: 1, plate: 'KDE1836', status: TripStatus.active)],
        totalCount: 1,
      ),
    );

    await tester.tap(find.text('Trips'));
    await tester.pumpAndSettle();

    // An open trip is the one thing here about the present. It must not render as a
    // completed trip with blank fare fields.
    expect(find.byType(TripCard), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('an empty trip list explains itself rather than going blank', (
    tester,
  ) async {
    await pumpActivity(tester, trips: const MyTripsState());

    await tester.tap(find.text('Trips'));
    await tester.pumpAndSettle();

    expect(find.byType(ClayEmptyState), findsOneWidget);
    expect(find.byType(TripCard), findsNothing);
  });

  testWidgets('a cached list says so instead of passing stale rows off as live', (
    tester,
  ) async {
    await pumpActivity(
      tester,
      trips: MyTripsState(
        trips: [_trip(id: 1, plate: 'KDE1836')],
        totalCount: 1,
        isFromCache: true,
      ),
    );

    await tester.tap(find.text('Trips'));
    await tester.pumpAndSettle();

    // Silence here is how a user concludes a toll was never charged.
    expect(find.byType(ClayBanner), findsWidgets);
  });

  testWidgets('the segment survives a tablet-width viewport', (tester) async {
    await pumpActivity(
      tester,
      trips: MyTripsState(trips: [_trip(id: 1, plate: 'KDE1836')], totalCount: 1),
      size: const Size(900, 1200),
    );

    await tester.tap(find.text('Trips'));
    await tester.pumpAndSettle();
    expect(find.byType(TripCard), findsOneWidget);
  });
}
