import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/core/data/wallet_repository.dart';
import 'package:mtag_user_app/core/models/account.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/tag.dart';
import 'package:mtag_user_app/core/models/vehicle.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/dashboard/presentation/widgets/balance_hero_card.dart';
import 'package:mtag_user_app/features/dashboard/presentation/widgets/low_balance_banner.dart';
import 'package:mtag_user_app/features/shared/tag_status_badge.dart';
import 'package:mtag_user_app/features/tags/presentation/tags_screen.dart';
import 'package:mtag_user_app/features/transactions/presentation/widgets/transaction_row.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

import '../helpers/golden_harness.dart';

/// Urdu / RTL goldens.
///
/// These exist because the RTL bugs in an app like this are not layout bugs — they are
/// *correctness* bugs, and they are invisible unless someone who reads Urdu looks at the
/// screen. Specifically:
///
///  * A plate number (`KDE1836`), a tag serial, a TID and every money figure are mixed
///    letter/digit strings. An unconstrained `Text` in an RTL paragraph reverses their
///    visual order, turning `Rs. 1,250` into something unreadable and `KDE1836` into a
///    plate that does not exist. Everything of that kind is forced `TextDirection.ltr`.
///  * Directional icons (back, chevrons) have to flip; the leading/trailing sides of every
///    row have to swap.
///
/// A widget test can assert a string is present in an Urdu build. Only an image can show
/// that the string is the right way round.
void main() {
  setUpAll(loadClayFonts);

  Future<void> pumpUrdu(
    WidgetTester tester,
    Widget child, {
    Size size = const Size(420, 720),
  }) async {
    tester.view
      ..physicalSize = size
      ..devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: clayLightTheme(),
        locale: const Locale('ur'),
        localizationsDelegates: const [
          AppL10n.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: AppL10n.supportedLocales,
        home: Builder(
          builder: (context) => Scaffold(
            backgroundColor: ClayTheme.of(context).palette.base,
            body: SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(ClaySpace.gutter),
                child: child,
              ),
            ),
          ),
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 16));
  }

  testWidgets('the hero balance card in Urdu', (tester) async {
    await pumpUrdu(
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

    // The layout is genuinely RTL...
    expect(
      Directionality.of(tester.element(find.byType(BalanceHeroCard))),
      TextDirection.rtl,
    );
    // ...and the figure is still readable left-to-right.
    expect(find.text('Rs. 4,250'), findsOneWidget);

    await expectLater(
      find.byType(MaterialApp),
      matchesGoldenFile('goldens/rtl_hero_card_urdu.png'),
    );
  });

  testWidgets('the low-balance banner in Urdu names the plate LTR', (
    tester,
  ) async {
    await pumpUrdu(
      tester,
      LowBalanceBanner(
        blocked: [_vehicle(plate: 'KDE1836', balance: '42.00')],
        low: [_vehicle(plate: 'KDE1837', balance: '150.00', id: 2)],
        onTopUp: (_) {},
      ),
    );

    // The plate must survive intact — a reversed registration number is a different
    // vehicle, and this banner exists to tell someone which of theirs is blocked.
    expect(find.textContaining('KDE1836'), findsWidgets);

    await expectLater(
      find.byType(MaterialApp),
      matchesGoldenFile('goldens/rtl_low_balance_urdu.png'),
    );
  });

  testWidgets('a tag row in Urdu keeps its serial and balance readable', (
    tester,
  ) async {
    await pumpUrdu(
      tester,
      TagListTile(
        vehicle: _vehicle(plate: 'KDE1836', balance: '1250.00'),
      ),
    );

    expect(find.text('Rs. 1,250'), findsOneWidget);

    await expectLater(
      find.byType(MaterialApp),
      matchesGoldenFile('goldens/rtl_tag_row_urdu.png'),
    );
  });

  testWidgets('a transaction row in Urdu signs the amount correctly', (
    tester,
  ) async {
    await pumpUrdu(
      tester,
      ClayCard(
        padding: const EdgeInsets.symmetric(vertical: ClaySpace.sm),
        child: Column(
          children: [
            TransactionRow(
              transaction: Transaction(
                id: 1,
                type: TransactionType.tollDeduction,
                amount: Decimal.parse('120.00'),
                status: TransactionStatus.success,
                source: TransactionSource.offlineExitSync,
                balanceAfter: Decimal.parse('1250.00'),
                processedAt: DateTime.utc(2026, 8, 14, 15, 30),
                plateNumber: 'KDE1836',
              ),
              showPlate: true,
            ),
            TransactionRow(
              transaction: Transaction(
                id: 2,
                type: TransactionType.topup,
                amount: Decimal.parse('1000.00'),
                status: TransactionStatus.success,
                source: TransactionSource.topupJazzCash,
                balanceAfter: Decimal.parse('1370.00'),
                processedAt: DateTime.utc(2026, 8, 14, 9, 5),
                plateNumber: 'KDE1836',
              ),
              showPlate: true,
            ),
          ],
        ),
      ),
    );

    // The minus stays on the left of the digits even in RTL.
    expect(find.text('− Rs. 120'), findsOneWidget);
    expect(find.text('+ Rs. 1,000'), findsOneWidget);

    await expectLater(
      find.byType(MaterialApp),
      matchesGoldenFile('goldens/rtl_transaction_rows_urdu.png'),
    );
  });

  testWidgets('status badges and fare classes render in Urdu', (tester) async {
    await pumpUrdu(
      tester,
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Wrap(
            spacing: ClaySpace.sm,
            runSpacing: ClaySpace.sm,
            children: [
              TagStatusBadge(tag: _tag()),
              TagStatusBadge(
                tag: _tag(status: TagStatus.expired, isValid: false),
              ),
              const TagStatusBadge(tag: null),
            ],
          ),
          const SizedBox(height: ClaySpace.lg),
          const Wrap(
            spacing: ClaySpace.sm,
            runSpacing: ClaySpace.sm,
            children: [
              FareClassPill(vehicleType: VehicleType.car),
              FareClassPill(vehicleType: VehicleType.truck4Axle),
              FareClassPill(vehicleType: VehicleType.motorcycle),
            ],
          ),
        ],
      ),
      size: const Size(420, 400),
    );

    await expectLater(
      find.byType(MaterialApp),
      matchesGoldenFile('goldens/rtl_badges_urdu.png'),
    );
  });
}

Tag _tag({TagStatus status = TagStatus.active, bool isValid = true}) => Tag(
  id: 1,
  tagSerial: 'SER0001',
  status: status,
  isValid: isValid,
  expiryDate: DateTime.utc(2099, 12, 31),
);

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
  tag: _tag(),
  accountId: id,
  balance: Decimal.parse(balance),
);
