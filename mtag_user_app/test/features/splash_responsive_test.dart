import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/core/errors/app_failure.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/auth/presentation/session_controller.dart';
import 'package:mtag_user_app/features/auth/presentation/splash_screen.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// The splash screen at every viewport it will actually meet.
///
/// This file exists because of a specific bug that had no test and was invisible on the
/// only device it was checked on. A `Scaffold` hands `body` **loose** horizontal
/// constraints and pins the result to the LEFT edge, so a page whose widest child was a
/// fixed 320px box collapsed to 320 and sat against the left of the screen. On a 360dp
/// phone the clamp hid it completely; on a tablet, a foldable, or any phone in landscape
/// the whole splash was jammed into the left third.
///
/// Nothing threw. There was no overflow, no red box, no console warning — the layout was
/// perfectly valid and simply in the wrong place. That is why the assertions here are about
/// POSITION and WIDTH rather than about the absence of errors: an error-only test would
/// have passed throughout.
class _Pending extends SessionController {
  @override
  Future<SessionState> build() => Completer<SessionState>().future;
}

class _Failing extends SessionController {
  @override
  Future<SessionState> build() async =>
      throw const NetworkFailure(message: 'no route to host');
}

void main() {
  /// Every viewport class the app ships to.
  const viewports = <String, Size>{
    'small phone': Size(320, 568),
    'phone': Size(360, 640),
    'tall phone': Size(412, 915),
    'phone landscape': Size(915, 412),
    'tablet': Size(800, 1280),
    'tablet landscape': Size(1280, 800),
  };

  Future<List<String>> pumpSplash(
    WidgetTester tester, {
    required Size size,
    required double textScale,
    required bool failing,
  }) async {
    tester.view
      ..physicalSize = size
      ..devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    // Collected rather than thrown, so one test reports every overflow at once instead of
    // stopping at the first.
    final errors = <String>[];
    final previous = FlutterError.onError;
    FlutterError.onError = (details) => errors.add(details.exceptionAsString());
    addTearDown(() => FlutterError.onError = previous);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          sessionControllerProvider.overrideWith(
            failing ? _Failing.new : _Pending.new,
          ),
        ],
        child: MediaQuery(
          data: MediaQueryData(
            size: size,
            textScaler: TextScaler.linear(textScale),
          ),
          child: MaterialApp(
            theme: clayDarkTheme(),
            localizationsDelegates: const [
              AppL10n.delegate,
              GlobalMaterialLocalizations.delegate,
              GlobalWidgetsLocalizations.delegate,
              GlobalCupertinoLocalizations.delegate,
            ],
            supportedLocales: AppL10n.supportedLocales,
            home: const SplashScreen(),
          ),
        ),
      ),
    );
    // Past the end of the 900ms reveal, so the assertions see the settled frame.
    await tester.pump(const Duration(milliseconds: 1200));
    return errors;
  }

  group('fills the viewport instead of collapsing to its widest child', () {
    for (final entry in viewports.entries) {
      testWidgets('${entry.key} ${entry.value.width.toInt()}x'
          '${entry.value.height.toInt()}', (tester) async {
        await pumpSplash(
          tester,
          size: entry.value,
          textScale: 1,
          failing: false,
        );

        // THE regression assertion. Before the fix this was 384 on every viewport wider
        // than 384, regardless of the actual screen width.
        final page = tester.getRect(find.byType(ClayAmbient));
        expect(
          page.width,
          entry.value.width,
          reason:
              'the page must span the screen; a short width means it collapsed to '
              'its content and is pinned to one edge',
        );
        expect(page.left, 0);
      });
    }
  });

  group('content is centred, not merely present', () {
    for (final entry in viewports.entries) {
      testWidgets(entry.key, (tester) async {
        await pumpSplash(
          tester,
          size: entry.value,
          textScale: 1,
          failing: false,
        );

        final expected = entry.value.width / 2;
        for (final (label, finder) in [
          ('mark', find.byType(Image)),
          ('progress bar', find.byType(LinearProgressIndicator)),
        ]) {
          expect(
            tester.getRect(finder.first).center.dx,
            moreOrLessEquals(expected, epsilon: 1),
            reason: '$label is off-centre on ${entry.key}',
          );
        }
      });
    }
  });

  group('the mark is bounded by both axes', () {
    testWidgets('never exceeds the size it was designed at', (tester) async {
      await pumpSplash(
        tester,
        size: const Size(1280, 800),
        textScale: 1,
        failing: false,
      );
      // A tablet must not scale the logo up to fill the space — an oversized mark is how
      // a phone layout stretched onto a tablet announces itself.
      expect(tester.getRect(find.byType(Image).first).width, lessThanOrEqualTo(230));
    });

    testWidgets('shrinks for a short viewport rather than overflowing', (
      tester,
    ) async {
      await pumpSplash(
        tester,
        size: const Size(915, 412),
        textScale: 1,
        failing: false,
      );
      // 412 tall leaves no room for the full-size mark plus the wordmark and the progress
      // line. Height has to win here even though width has room to spare.
      expect(tester.getRect(find.byType(Image).first).width, lessThan(200));
    });
  });

  group('no overflow in either state, at any size, at any font scale', () {
    for (final entry in viewports.entries) {
      for (final scale in [1.0, 1.3, 2.0]) {
        for (final failing in [false, true]) {
          final state = failing ? 'offline' : 'checking';
          testWidgets('${entry.key} @${scale}x ($state)', (tester) async {
            final errors = await pumpSplash(
              tester,
              size: entry.value,
              textScale: scale,
              failing: failing,
            );
            expect(
              errors,
              isEmpty,
              reason: 'layout errors on ${entry.key} @${scale}x ($state)',
            );
          });
        }
      }
    }
  });

  group('the offline state stays usable', () {
    testWidgets('Retry is reachable in landscape at a large font scale', (
      tester,
    ) async {
      await pumpSplash(
        tester,
        size: const Size(915, 412),
        textScale: 2,
        failing: true,
      );

      // The point of the scrollable error layout. A splash that cannot show its own Retry
      // button is a dead end — the user's only recourse would be force-quitting the app.
      final retry = find.byType(ClayButton);
      expect(retry, findsWidgets);
      await tester.ensureVisible(retry.first);
      expect(tester.takeException(), isNull);
    });
  });
}
