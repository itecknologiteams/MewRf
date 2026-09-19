import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:mtag_user_app/core/cache/cache_database.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/user.dart';
import 'package:mtag_user_app/core/network/api_client.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/core/router/app_router.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/auth/presentation/biometric_gate.dart';
import 'package:mtag_user_app/features/auth/presentation/login_screen.dart';
import 'package:mtag_user_app/features/auth/presentation/session_controller.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Signing in must NAVIGATE, not merely create a session.
///
/// The reported symptom: login succeeds and the cookies land, but the screen stays on the
/// login form — and a cold restart then goes straight to the dashboard. That is the exact
/// signature of session state changing without the router being told to re-evaluate: the
/// jar is correct, so the next launch's probe routes properly, while the live session change
/// went unnoticed.
class _Session extends SessionController {
  _Session(this._initial);

  final SessionState _initial;

  @override
  Future<SessionState> build() async => _initial;

  void signInForTest() => state = const AsyncValue.data(
    SessionSignedIn(
      AppUser(
        id: 2,
        uuid: 'u',
        fullName: 'Ali',
        phone: '03211213351',
        role: UserRole.user,
        status: UserStatus.active,
      ),
    ),
  );
}

class _MockApiClient extends Mock implements ApiClient {}

class _MockCache extends Mock implements CacheDatabase {}

class _OpenGate extends BiometricGate {
  @override
  Future<BiometricGateState> build() async =>
      const BiometricGateState.notRequired();
}

void main() {
  testWidgets('a session created while on /login redirects to the dashboard', (
    tester,
  ) async {
    final session = _Session(const SessionSignedOut());
    final container = ProviderContainer(
      overrides: [
        // Seeded because `main()` normally does it from ApiClient.create(), and the
        // dashboard's repositories read it the moment the router lands there. Without this
        // the test dies on the destination rather than on the thing under test.
        apiClientProvider.overrideWithValue(_MockApiClient()),
        cacheDatabaseProvider.overrideWithValue(_MockCache()),
        sessionControllerProvider.overrideWith(() => session),
        biometricGateProvider.overrideWith(_OpenGate.new),
      ],
    );
    addTearDown(container.dispose);

    final router = container.read(routerProvider);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(
          routerConfig: router,
          theme: clayDarkTheme(),
          localizationsDelegates: const [
            AppL10n.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          supportedLocales: AppL10n.supportedLocales,
        ),
      ),
    );
    await tester.pumpAndSettle();

    // PUSHED, exactly as onboarding_screen does it. This is the crux: with `go` the test
    // would pass even with the bug present, because the redirect governs the declarative
    // location and there would be no imperative page left on top to hide the dashboard.
    unawaited(router.push(Routes.login));
    await tester.pumpAndSettle();
    expect(
      find.byType(LoginScreen),
      findsOneWidget,
      reason: 'precondition: the login screen must be on screen',
    );

    // Asserted on the WIDGET, not on `currentConfiguration.uri`: for an imperative push
    // go_router reports the underlying declarative location, so the URI looks like
    // /welcome while /login is what the user is actually looking at. The URI would
    // therefore have said "redirected" while the login form was still covering the
    // dashboard — which is precisely the bug.
    //
    // What SessionController.signIn does on a successful login.
    session.signInForTest();

    // Long enough to outlast the page transition (ClayMotion.page is 260ms) — a page that
    // is merely animating out is still 'found' by the finder.
    for (var i = 0; i < 20; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }

    // The dashboard's own providers cannot build in a unit test: apiClientProvider is
    // deliberately an unoverridden throw, because it must be seeded in main() from
    // ApiClient.create(). Drained rather than asserted on — reaching the dashboard at all
    // is the success condition here, and what it does once there is other tests' business.
    while (tester.takeException() != null) {}

    expect(
      find.byType(LoginScreen),
      findsNothing,
      reason:
          'a pushed login page must not survive the session becoming SignedIn — leaving '
          'it there is why login appeared to do nothing until the app was restarted',
    );
  });
}
