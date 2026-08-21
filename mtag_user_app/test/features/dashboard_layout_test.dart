import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/core/data/wallet_repository.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/tag.dart';
import 'package:mtag_user_app/core/models/vehicle.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/dashboard/presentation/wallet_controller.dart';
import 'package:mtag_user_app/features/dashboard/presentation/widgets/balance_hero_card.dart';
import 'package:mtag_user_app/features/dashboard/presentation/widgets/low_balance_banner.dart';
import 'package:mtag_user_app/features/dashboard/presentation/widgets/stat_tiles.dart';
import 'package:mtag_user_app/features/dashboard/presentation/widgets/tag_rail.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Layout tests for the dashboard's building blocks.
///
/// The dashboard is a vertical `ListView`, which hands every child **unbounded height**.
/// A widget that is fine inside a `Column` on a fixed-height screen can throw
/// "BoxConstraints forces an infinite height" there — and when it does, the ListView's
/// sliver fails `child.hasSize`, so the whole screen renders blank rather than showing an
/// error box. Silent blankness is why this needs its own test: nothing in the widget tests
/// that assert on text would have caught it.
///
/// Each case pumps one widget inside a genuinely unbounded parent, which is the exact
/// constraint the dashboard applies.
void main() {
  setUpAll(() {
    // A layout error must FAIL the test rather than print and continue. Flutter's default
    // handler logs and carries on, which is exactly how the blank dashboard shipped: the
    // exception was on the console and the screen was simply empty.
    FlutterError.onError = (details) =>
        fail('Layout error: ${details.exceptionAsString()}');
  });

  Future<void> pumpUnbounded(WidgetTester tester, Widget child) async {
    tester.view
      ..physicalSize = const Size(420, 900)
      ..devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          theme: clayLightTheme(),
          localizationsDelegates: const [
            AppL10n.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          supportedLocales: AppL10n.supportedLocales,
          home: Scaffold(
            // A vertical ListView — the dashboard's actual parent, and what makes the
            // height unbounded.
            body: ListView(children: [child]),
          ),
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 16));
  }

  testWidgets('BalanceHeroCard survives unbounded height', (tester) async {
    await pumpUnbounded(
      tester,
      BalanceHeroCard(
        total: WalletTotal(
          total: Decimal.parse('4250.00'),
          walletCount: 3,
          isPartial: false,
        ),
        tagCount: 3,
        onTopUp: () {},
      ),
    );
    expect(find.text('Rs. 4,250'), findsOneWidget);
  });

  testWidgets('LowBalanceBanner survives unbounded height', (tester) async {
    await pumpUnbounded(
      tester,
      LowBalanceBanner(
        blocked: [_vehicle(plate: 'KDE1836', balance: '42.00')],
        low: const [],
        onTopUp: (_) {},
      ),
    );
    expect(find.textContaining('KDE1836'), findsWidgets);
  });

  testWidgets('TagRail survives unbounded height', (tester) async {
    // The prime suspect: a horizontally scrolling rail of cards, where each card's Column
    // uses a Spacer. A Spacer needs a bounded main axis.
    await pumpUnbounded(
      tester,
      TagRail(
        vehicles: [
          _vehicle(plate: 'KDE1836', balance: '1250.00'),
          _vehicle(plate: 'KDE1837', balance: '42.00', id: 2),
        ],
      ),
    );
    expect(find.text('KDE1836'), findsOneWidget);
  });

  testWidgets('StatTiles survives unbounded height', (tester) async {
    // THE regression this file exists for.
    //
    // StatTiles wants three equal-height tiles, which `CrossAxisAlignment.stretch`
    // expresses — but in the dashboard's vertical ListView the Row's cross axis is
    // vertical and unbounded, so stretch demanded infinite height. The sliver then failed
    // `child.hasSize` and the whole dashboard rendered BLANK, with no on-screen error.
    // IntrinsicHeight bounds the Row so stretch has something finite to work against.
    await pumpUnbounded(
      tester,
      StatTiles(
        snapshot: WalletSnapshot(
          vehicles: [
            _vehicle(plate: 'KDE1836', balance: '1250.00'),
            _vehicle(plate: 'KDE1837', balance: '42.00', id: 2),
          ],
          total: WalletTotal(
            total: Decimal.parse('1292.00'),
            walletCount: 2,
            isPartial: false,
          ),
          summary: null,
          isStale: false,
        ),
      ),
    );

    expect(find.text('Tags'), findsOneWidget);
    expect(find.text('Vehicles'), findsOneWidget);

    // Equal height is the reason stretch was there; assert it still holds.
    final heights = tester
        .widgetList<ClayCard>(find.byType(ClayCard))
        .map((_) => 0)
        .toList();
    expect(heights.length, 3);
    final sizes = tester
        .renderObjectList<RenderBox>(find.byType(ClayCard))
        .map((box) => box.size.height)
        .toSet();
    expect(
      sizes.length,
      1,
      reason: 'all three tiles should be the same height',
    );
  });

  testWidgets('ClayEmptyState survives unbounded height', (tester) async {
    // Starts with a Center, which expands to fill — infinite when the height is unbounded.
    await pumpUnbounded(
      tester,
      const ClayEmptyState(
        icon: Icons.sensors_off_rounded,
        title: 'No tags yet',
        message: 'They appear here once fitted.',
      ),
    );
    expect(find.text('No tags yet'), findsOneWidget);
  });

  testWidgets('ClayErrorState survives unbounded height', (tester) async {
    await pumpUnbounded(
      tester,
      ClayErrorState(message: 'No connection', onRetry: () {}),
    );
    expect(find.text('No connection'), findsOneWidget);
  });

  testWidgets('a ClayCard with a Spacer survives unbounded height', (
    tester,
  ) async {
    // The minimal reproduction, independent of any feature widget.
    await pumpUnbounded(
      tester,
      const SizedBox(
        height: 176,
        child: ClayCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('top'),
              Spacer(),
              Text('bottom'),
            ],
          ),
        ),
      ),
    );
    expect(find.text('bottom'), findsOneWidget);
  });
}

MyVehicle _vehicle({
  required String plate,
  required String balance,
  int id = 1,
}) => MyVehicle(
  id: id,
  plateNumber: plate,
  vehicleType: VehicleType.car,
  status: VehicleStatus.active,
  registeredAt: DateTime.utc(2026, 3),
  tag: Tag(
    id: id,
    tagSerial: 'SER000$id',
    status: TagStatus.active,
    isValid: true,
    expiryDate: DateTime.utc(2099, 12, 31),
  ),
  accountId: id,
  balance: Decimal.parse(balance),
);
