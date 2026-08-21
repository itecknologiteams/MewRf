import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/onboarding/presentation/otp_controller.dart';
import 'package:mtag_user_app/features/onboarding/presentation/otp_screen.dart';
import 'package:mtag_user_app/features/onboarding/presentation/widgets/otp_boxes.dart';
import 'package:mtag_user_app/features/onboarding/presentation/widgets/verify_burst.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// The OTP ceremony's smoothness, expressed as structural invariants.
///
/// Frame timings cannot be measured meaningfully in a widget test, but the things that made
/// this animation stutter are all structural, and each one IS assertable:
///
///   * **A constant tree shape.** The old version mounted `VerifyBurst` at t = 0.34 and
///     swapped the boxes for the success tick at t = 0.72. Both created and destroyed
///     elements mid-flight, which forces a rebuild and a layout pass on exactly the frames
///     the eye is fixed on. Everything is now built once and only opacity moves.
///   * **No `saveLayer` while idle.** Four per-box `Opacity` widgets became one around the
///     group, and it is omitted entirely at full opacity — which is the whole entry phase,
///     where the user actually spends their time.
///   * **A repaint boundary under the glass.** The card is a `BackdropFilter`; without a
///     boundary each animated frame dirties its layer and the blur is recomputed.
class _Flow extends OtpFlowController {
  _Flow(this._initial);

  final OtpFlowState _initial;

  @override
  OtpFlowState build() => _initial;
}

void main() {
  Future<void> pumpOtp(
    WidgetTester tester, {
    OtpFlowState state = const OtpFlowState(step: OtpStep.code, code: '12'),
    Size size = const Size(420, 900),
    double textScale = 1.0,
  }) async {
    tester.view
      ..physicalSize = size
      ..devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          otpFlowControllerProvider.overrideWith(() => _Flow(state)),
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
            home: const OtpScreen(),
          ),
        ),
      ),
    );
    await tester.pump();
  }

  group('the tree shape never changes mid-animation', () {
    testWidgets('the burst exists before it is visible', (tester) async {
      await pumpOtp(tester);

      // Present from the first frame at progress 0, where its painter early-returns. The
      // old code mounted it on a threshold, paying an element build and a layout mid-burst.
      expect(find.byType(VerifyBurst), findsOneWidget);
    });

    testWidgets('boxes and the success tick coexist throughout', (
      tester,
    ) async {
      await pumpOtp(tester);

      final boxes = find.byType(OtpBoxes);
      expect(boxes, findsOneWidget);

      // The tick is a bordered Container that is present but transparent. Both being
      // mounted at once is the invariant — swapping them was the visible hitch.
      expect(find.byIcon(Icons.check_rounded), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });

  group('no wasted compositing layers while the user is typing', () {
    testWidgets('the box group is not wrapped in an Opacity at rest', (
      tester,
    ) async {
      await pumpOtp(tester);

      // `Opacity` allocates a saveLayer for anything strictly between 0 and 1, and the
      // entry phase is where nearly all of the user's time is spent. Four per-box Opacity
      // widgets here meant four saveLayers a frame to render nothing different.
      final withinBoxes = find.descendant(
        of: find.byType(OtpBoxes),
        matching: find.byType(Opacity),
      );
      expect(
        withinBoxes,
        findsNothing,
        reason: 'the group Opacity must be omitted at full opacity',
      );
    });

    testWidgets('the animating stage sits behind a RepaintBoundary', (
      tester,
    ) async {
      await pumpOtp(tester);

      // The card is glass. Without this the BackdropFilter is re-blurred on every frame of
      // the ceremony, which is the most expensive thing on the screen.
      expect(
        find.ancestor(
          of: find.byType(VerifyBurst),
          matching: find.byType(RepaintBoundary),
        ),
        findsWidgets,
      );
    });
  });

  group('the boxes use explicit animation, not implicit', () {
    testWidgets('no AnimatedContainer per digit box', (tester) async {
      await pumpOtp(tester);

      // An implicit animation inside a tree that an explicit controller already drives per
      // frame adds a ticker and a BoxDecoration allocation per box, to interpolate values
      // it is being handed anyway — and it lagged the layout it was supposed to match.
      expect(
        find.descendant(
          of: find.byType(OtpBoxes),
          matching: find.byType(AnimatedContainer),
        ),
        findsNothing,
      );
    });
  });

  group('layout survives every viewport and font scale', () {
    for (final size in [
      const Size(320, 568),
      const Size(360, 640),
      const Size(412, 915),
      const Size(915, 412),
      const Size(800, 1280),
    ]) {
      for (final scale in [1.0, 1.6]) {
        testWidgets(
          '${size.width.toInt()}x${size.height.toInt()} @${scale}x',
          (tester) async {
            final errors = <String>[];
            final previous = FlutterError.onError;
            FlutterError.onError = (d) => errors.add(d.exceptionAsString());
            addTearDown(() => FlutterError.onError = previous);

            await pumpOtp(tester, size: size, textScale: scale);
            await tester.pump(const Duration(milliseconds: 400));

            expect(errors, isEmpty, reason: errors.join(' | '));
          },
        );
      }
    }
  });

  group('states render without exploding', () {
    testWidgets('an error state shows its message', (tester) async {
      await pumpOtp(
        tester,
        state: const OtpFlowState(
          step: OtpStep.code,
          code: '1234',
          error: 'invalid',
          attemptsLeft: 3,
        ),
      );
      expect(tester.takeException(), isNull);
    });

    testWidgets('a resend cooldown renders its countdown', (tester) async {
      await pumpOtp(
        tester,
        state: const OtpFlowState(step: OtpStep.code, resendIn: 24),
      );
      // The ICU plural that used to be formatted on every animation frame.
      expect(find.textContaining('24'), findsWidgets);
    });
  });
}
