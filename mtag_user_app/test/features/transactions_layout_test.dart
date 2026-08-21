import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/core/models/account.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/transactions/presentation/widgets/transaction_row.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Reproduces the Activity screen's sliver layout.
///
/// The screen groups transactions into one `SliverMainAxisGroup` per day, each with a
/// PINNED `SliverPersistentHeader`. On device that produced a flood of
/// "SliverGeometry is not valid: layoutExtent exceeds paintExtent" plus null-check
/// crashes, several per frame — and, like the blank dashboard, nothing on screen said so,
/// because Flutter's default error handler logs and carries on.
///
/// This builds the same sliver tree and SCROLLS it, which is what the on-device errors
/// needed: a pinned header only misbehaves once its group starts leaving the viewport.
void main() {
  setUpAll(() {
    FlutterError.onError = (details) =>
        fail('Layout error: ${details.exceptionAsString()}');
  });

  Future<void> pumpList(
    WidgetTester tester, {
    required int days,
    double textScale = 1.0,
  }) async {
    tester.platformDispatcher.textScaleFactorTestValue = textScale;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);

    tester.view
      ..physicalSize = const Size(420, 840)
      ..devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      MaterialApp(
        theme: clayLightTheme(),
        localizationsDelegates: const [
          AppL10n.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: AppL10n.supportedLocales,
        home: Scaffold(
          body: CustomScrollView(
            slivers: [
              for (var d = 0; d < days; d++) ...[
                SliverPadding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: ClaySpace.gutter,
                  ),
                  sliver: SliverPersistentHeader(
                    pinned: true,
                    delegate: _DayHeaderDelegate(
                      day: DateTime.utc(2026, 8, 14 - d),
                      extent: _headerExtent(textScale),
                    ),
                  ),
                ),
                SliverPadding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: ClaySpace.gutter,
                  ),
                  sliver: SliverToBoxAdapter(
                    child: ClayCard(
                      padding: const EdgeInsets.symmetric(
                        vertical: ClaySpace.sm,
                      ),
                      child: Column(
                        children: [
                          for (var i = 0; i < 4; i++)
                            TransactionRow(
                              transaction: _txn(id: d * 10 + i),
                              showPlate: true,
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('renders day groups without sliver errors', (tester) async {
    await pumpList(tester, days: 4);
    expect(find.byType(TransactionRow), findsWidgets);
  });

  testWidgets('scrolling past a pinned header does not break geometry', (
    tester,
  ) async {
    // The failing case: the group's pinned header stays put while its body scrolls away.
    await pumpList(tester, days: 6);

    for (var i = 0; i < 6; i++) {
      await tester.drag(find.byType(CustomScrollView), const Offset(0, -220));
      await tester.pump();
    }
    await tester.pumpAndSettle();

    expect(find.byType(TransactionRow), findsWidgets);
  });

  testWidgets('a large text scale does not overflow the fixed-height header', (
    tester,
  ) async {
    // The extent used to be hardcoded at 44. A user running large system text made the
    // header's content taller than that, and a persistent header CLIPS rather than
    // growing — so the date was cut in half. The screen now measures it.
    await pumpList(tester, days: 3, textScale: 2);
    expect(find.byType(TransactionRow), findsWidgets);
  });
}

/// Mirrors the shipping delegate's contract: a fixed extent it must state up front.
class _DayHeaderDelegate extends SliverPersistentHeaderDelegate {
  const _DayHeaderDelegate({required this.day, required this.extent});

  final DateTime day;
  final double extent;

  @override
  double get minExtent => extent;

  @override
  double get maxExtent => extent;

  @override
  Widget build(BuildContext context, double shrinkOffset, bool overlaps) =>
      DayHeader(day: day);

  @override
  bool shouldRebuild(_DayHeaderDelegate old) =>
      old.day != day || old.extent != extent;
}

/// The same measurement the screen makes, at whatever text scale the test set.
double _headerExtent(double textScale) {
  const verticalPadding = ClaySpace.lg + ClaySpace.sm;
  return verticalPadding + (13.0 * textScale * 1.3).ceilToDouble();
}

Transaction _txn({required int id}) => Transaction(
  id: id,
  type: TransactionType.tollDeduction,
  amount: Decimal.parse('150.00'),
  balanceBefore: Decimal.parse('1000.00'),
  balanceAfter: Decimal.parse('850.00'),
  status: TransactionStatus.success,
  source: TransactionSource.offlineExitSync,
  tagSerial: 'SER0001',
  plateNumber: 'KDE1836',
  processedAt: DateTime.utc(2026, 8, 14, 9, 30),
);
