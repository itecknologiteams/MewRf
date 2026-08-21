import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/topup.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/shared/money_text.dart';
import 'package:mtag_user_app/features/topup/domain/payment_gateway.dart';
import 'package:mtag_user_app/features/topup/presentation/topup_controller.dart';
import 'package:mtag_user_app/features/topup/presentation/widgets/amount_step.dart';
import 'package:mtag_user_app/features/topup/presentation/widgets/gateway_list.dart';
import 'package:mtag_user_app/features/topup/presentation/widgets/pending_topups.dart';
import 'package:mtag_user_app/features/topup/presentation/widgets/topup_progress_view.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

import '../helpers/golden_harness.dart';

/// Widget tests for the top-up flow, with the pending and timeout branches covered.
///
/// Those two branches are the point. They are the states an implementation that assumed
/// payments complete synchronously would never render, and this app reaches them
/// constantly — the aggregator flow has no completion signal the app can see, and the
/// app-initiated flow has no checkout URL configured.
void main() {
  setUpAll(loadClayFonts);

  Future<void> pump(WidgetTester tester, Widget child) async {
    tester.view
      ..physicalSize = const Size(420, 1400)
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
        // A finite viewport, not a SingleChildScrollView: the widgets under test include
        // ListViews, and nesting one in an unbounded scroll view lays out zero children.
        home: Scaffold(
          body: SizedBox(
            height: 1400,
            child: child,
          ),
        ),
      ),
    );
    await tester.pump(const Duration(milliseconds: 16));
  }

  group('AmountStep', () {
    testWidgets('the Pay button is disabled until an amount is chosen', (
      tester,
    ) async {
      await pump(
        tester,
        AmountStep(
          amount: null,
          currentBalance: Decimal.parse('120.00'),
          onChanged: (_) {},
          onSubmit: () {},
        ),
      );

      final button = tester.widget<ClayButton>(
        find.widgetWithText(ClayButton, 'Top Up'),
      );
      expect(button.onPressed, isNull);
    });

    testWidgets('below Rs. 100 shows the server minimum and blocks submission', (
      tester,
    ) async {
      // The rule is enforced server-side twice (InitiateTopupSerializer and
      // JazzCashService.initiate_topup). Enforcing it here too means the user is warned
      // rather than bounced.
      var submitted = false;
      await pump(
        tester,
        AmountStep(
          amount: Decimal.parse('50'),
          currentBalance: Decimal.parse('120.00'),
          errorKey: 'min',
          onChanged: (_) {},
          onSubmit: () => submitted = true,
        ),
      );

      expect(
        find.textContaining('Minimum top-up amount is Rs. 100'),
        findsWidgets,
      );

      final button = tester.widget<ClayButton>(
        find.widgetWithText(ClayButton, 'Top Up'),
      );
      expect(button.onPressed, isNull);
      expect(submitted, isFalse);
    });

    testWidgets('a valid amount previews the balance after top-up', (
      tester,
    ) async {
      await pump(
        tester,
        AmountStep(
          amount: Decimal.parse('500'),
          currentBalance: Decimal.parse('120.00'),
          onChanged: (_) {},
          onSubmit: () {},
        ),
      );

      // 120 + 500. A PREVIEW — nothing has been credited, and the displayed balance
      // elsewhere is untouched.
      expect(find.text('Rs. 620'), findsOneWidget);

      final button = tester.widget<ClayButton>(
        find.widgetWithText(ClayButton, 'Top Up'),
      );
      expect(button.onPressed, isNotNull);
    });

    testWidgets('states that balances come from the server', (tester) async {
      await pump(
        tester,
        AmountStep(
          amount: Decimal.parse('500'),
          currentBalance: Decimal.parse('120.00'),
          onChanged: (_) {},
          onSubmit: () {},
        ),
      );
      expect(
        find.textContaining('always read from the server'),
        findsOneWidget,
      );
    });

    testWidgets('presets are offered and none is below the minimum', (
      tester,
    ) async {
      await pump(
        tester,
        AmountStep(
          amount: null,
          currentBalance: Decimal.parse('0.00'),
          onChanged: (_) {},
          onSubmit: () {},
        ),
      );

      expect(find.text('Rs. 500'), findsOneWidget);
      expect(find.text('Rs. 1,000'), findsOneWidget);
      expect(find.text('Rs. 5,000'), findsOneWidget);
      // Rs. 50 would be rejected by the server, so it is never offered.
      expect(find.text('Rs. 50'), findsNothing);
    });
  });

  group('TopupProgressView', () {
    TopupState state(TopupProgress progress) =>
        TopupState(accountId: 1, progress: progress);

    testWidgets(
      'WAITING shows the pending state and the instructions that work',
      (tester) async {
        await pump(
          tester,
          TopupProgressView(
            state: state(
              TopupWaitingForConfirmation(
                topupId: 42,
                amount: Decimal.parse('500'),
                attempt: 1,
              ),
            ),
            vehicle: null,
            onDone: () {},
            onRetry: () {},
            onCheckAgain: () async {},
          ),
        );

        expect(find.text('Waiting for payment confirmation'), findsOneWidget);
        expect(find.textContaining('Rs. 500'), findsWidgets);
        // The waiting copy does say "as soon as the payment is confirmed" — that is the
        // promise, not a claim. What must NOT appear is the settled headline.
        expect(find.text('Top-up confirmed'), findsNothing);
        // Nor a balance, which would imply the money has landed.
        expect(find.byType(MoneyText), findsNothing);
      },
    );

    testWidgets(
      'WAITING with no TID hides the JazzCash block instead of blanking it',
      (tester) async {
        // Degrade gracefully: an older backend omits `tid` from TagSerializer, and an empty
        // field under "type this into JazzCash" is worse than no field.
        await pump(
          tester,
          TopupProgressView(
            state: state(
              TopupWaitingForConfirmation(
                topupId: 42,
                amount: Decimal.parse('500'),
                attempt: 1,
              ),
            ),
            vehicle: null,
            onDone: () {},
            onRetry: () {},
            onCheckAgain: () async {},
          ),
        );

        expect(find.text('TID not available'), findsOneWidget);
        expect(find.text('Top up from the JazzCash app'), findsNothing);
      },
    );

    testWidgets('TIMED OUT is not a failure and says not to pay again', (
      tester,
    ) async {
      await pump(
        tester,
        TopupProgressView(
          state: state(
            TopupTimedOut(topupId: 42, amount: Decimal.parse('500')),
          ),
          vehicle: null,
          onDone: () {},
          onRetry: () {},
          onCheckAgain: () async {},
        ),
      );

      expect(find.text('Still waiting'), findsOneWidget);
      expect(find.textContaining('do not need to pay again'), findsOneWidget);
      // Crucially NOT presented as a failure — the callback may still land.
      expect(find.text('Top-up did not go through'), findsNothing);
    });

    testWidgets('CONFIRMED shows the amount and a server-read balance', (
      tester,
    ) async {
      await pump(
        tester,
        TopupProgressView(
          state: state(
            TopupConfirmed(
              amount: Decimal.parse('500'),
              newBalance: Decimal.parse('620'),
            ),
          ),
          vehicle: null,
          onDone: () {},
          onRetry: () {},
          onCheckAgain: () async {},
        ),
      );

      expect(find.text('Top-up confirmed'), findsOneWidget);
      expect(find.text('Rs. 620'), findsOneWidget);
    });

    testWidgets('FAILED offers a retry', (tester) async {
      var retried = false;
      await pump(
        tester,
        TopupProgressView(
          state: state(
            const TopupFailed(reason: 'The payment did not go through.'),
          ),
          vehicle: null,
          onDone: () {},
          onRetry: () => retried = true,
          onCheckAgain: () async {},
        ),
      );

      expect(find.text('Top-up did not go through'), findsOneWidget);
      await tester.tap(find.widgetWithText(ClayButton, 'Retry'));
      expect(retried, isTrue);
    });
  });

  group('PendingTopups', () {
    testWidgets('lists unsettled top-ups so the user does not pay twice', (
      tester,
    ) async {
      await pump(
        tester,
        PendingTopups(
          pending: [
            TopupRequest(
              id: 1,
              amount: Decimal.parse('500'),
              status: TopupStatus.pending,
              requestedAt: DateTime.now().toUtc().subtract(
                const Duration(minutes: 4),
              ),
            ),
          ],
          onCheckAgain: () async {},
        ),
      );

      expect(find.text('Pending top-ups'), findsOneWidget);
      expect(find.textContaining('Rs. 500'), findsWidgets);
      expect(find.textContaining('4 minutes ago'), findsOneWidget);
    });
  });

  group('GatewayList', () {
    testWidgets('badges each method honestly', (tester) async {
      await pump(
        tester,
        GatewayList(
          selectedId: const JazzCashAggregatorGateway().id,
          gatewayContext: const GatewayContext(
            accountId: 1,
            plateNumber: 'KDE1836',
            tid: 'E28011700000021234ABCD',
          ),
          onSelect: (_) {},
        ),
      );

      // The aggregator flow and cash both work today.
      expect(find.text('Works now'), findsNWidgets(2));
      // Easypaisa and card have no backend at all.
      expect(find.text('Coming soon'), findsNWidgets(2));
      // App-initiated checkout has no URL configured.
      expect(find.text('Not set up'), findsOneWidget);
    });

    testWidgets('the JazzCash app option is listed first', (tester) async {
      await pump(
        tester,
        GatewayList(
          selectedId: null,
          gatewayContext: const GatewayContext(
            accountId: 1,
            plateNumber: 'KDE1836',
            tid: 'TID',
          ),
          onSelect: (_) {},
        ),
      );

      final titles = tester
          .widgetList<Text>(find.byType(Text))
          .map((t) => t.data)
          .whereType<String>()
          .toList();
      expect(
        titles.indexOf('JazzCash app') < titles.indexOf('Pay in this app'),
        isTrue,
      );
    });
  });
}
