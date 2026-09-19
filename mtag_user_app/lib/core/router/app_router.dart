import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mtag_user_app/core/data/auth_repository.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/auth/presentation/biometric_gate.dart';
import 'package:mtag_user_app/features/auth/presentation/login_screen.dart';
import 'package:mtag_user_app/features/auth/presentation/session_controller.dart';
import 'package:mtag_user_app/features/auth/presentation/signed_in_exit.dart';
import 'package:mtag_user_app/features/auth/presentation/splash_screen.dart';
import 'package:mtag_user_app/features/auth/presentation/unlock_screen.dart';
import 'package:mtag_user_app/features/dashboard/presentation/dashboard_screen.dart';
import 'package:mtag_user_app/features/fares/presentation/fares_screen.dart';
import 'package:mtag_user_app/features/onboarding/presentation/onboarding_screen.dart';
import 'package:mtag_user_app/features/onboarding/presentation/otp_screen.dart';
import 'package:mtag_user_app/features/onboarding/presentation/phone_entry_screen.dart';
import 'package:mtag_user_app/features/onboarding/presentation/set_password_screen.dart';
import 'package:mtag_user_app/features/plazas/presentation/plazas_screen.dart';
import 'package:mtag_user_app/features/profile/presentation/profile_screen.dart';
import 'package:mtag_user_app/features/shell/app_shell.dart';
import 'package:mtag_user_app/features/tags/presentation/tag_detail_screen.dart';
import 'package:mtag_user_app/features/tags/presentation/tags_screen.dart';
import 'package:mtag_user_app/features/topup/presentation/topup_screen.dart';
import 'package:mtag_user_app/features/transactions/presentation/transactions_screen.dart';
import 'package:mtag_user_app/features/trips/presentation/trips_screen.dart';
import 'package:mtag_user_app/features/vehicles/presentation/vehicle_detail_screen.dart';
import 'package:mtag_user_app/features/vehicles/presentation/vehicles_screen.dart';

/// Route paths, in one place so a deep link and a `go()` cannot disagree.
abstract final class Routes {
  static const splash = '/';
  static const login = '/login';
  static const unlock = '/unlock';

  // First-time password setup, for a tag holder whose account a booth created but who has
  // never been given a password.
  static const onboarding = '/welcome';
  static const phoneEntry = '/setup/phone';
  static const otp = '/setup/code';
  static const setPassword = '/setup/password';

  /// Forgot password. A separate path from [phoneEntry] rather than a query flag so the
  /// guard list below can name it, and so a deep link lands in the right flow.
  static const forgotPassword = '/reset/phone';
  static const dashboard = '/home';
  static const tags = '/tags';
  static const plazas = '/plazas';
  static const activity = '/activity';
  static const profile = '/profile';

  static const tagDetail = 'tag/:serial';
  static const vehicles = '/vehicles';
  static const vehicleDetail = '/vehicles/:id';
  static const trips = '/trips/:vehicleId';
  static const fares = '/fares';
  static const topup = '/topup';

  static String tagDetailPath(String serial) => '/tags/tag/$serial';

  static String vehicleDetailPath(int id) => '/vehicles/$id';

  static String tripsPath(int vehicleId) => '/trips/$vehicleId';

  static String topupPath({int? accountId}) =>
      accountId == null ? topup : '$topup?account=$accountId';
}

final _rootKey = GlobalKey<NavigatorState>();
final _shellKey = GlobalKey<NavigatorState>();

/// The router, with a redirect-based auth guard.
///
/// A redirect rather than per-screen checks: a screen that checks its own auth is a
/// screen someone can forget to add the check to, and every one of these screens
/// reads money.
/// Notifies GoRouter that a redirect decision may have changed.
///
/// See [routerProvider] for why the router itself must not be rebuilt.
class _RouterRefresh extends ChangeNotifier {
  void bump() => notifyListeners();
}

final routerProvider = Provider<GoRouter>((ref) {
  // ONE GoRouter for the app's lifetime. This provider must never rebuild.
  //
  // `_rootKey` and `_shellKey` are top-level GlobalKeys. Rebuilding this provider —
  // which is what `ref.watch` here would cause on every session or gate change —
  // constructs a SECOND GoRouter holding the same keys while the first is still
  // mounted. Two Navigators claiming one GlobalKey corrupts the element tree, and it
  // surfaces as `'_dependents.isEmpty': is not true` from InheritedElement.unmount —
  // a red screen with no hint that routing caused it.
  //
  // So: state is read inside `redirect` (which re-runs on demand) and a
  // refreshListenable tells GoRouter when to re-run it. `ref.listen` reacts to changes
  // WITHOUT making this provider depend on them.
  final refresh = _RouterRefresh();
  ref
    ..onDispose(refresh.dispose)
    ..listen(sessionControllerProvider, (_, _) => refresh.bump())
    ..listen(biometricGateProvider, (_, _) => refresh.bump());

  return GoRouter(
    navigatorKey: _rootKey,
    refreshListenable: refresh,
    initialLocation: Routes.splash,
    // Route logging, debug builds only. go_router prints each navigation and redirect
    // via dart:developer — visible in `flutter run` and DevTools, not in logcat.
    debugLogDiagnostics: kDebugMode,
    redirect: (context, state) {
      // Read, not watch: this closure runs per navigation and whenever `refresh` fires,
      // so it always sees current state without binding the provider to it.
      final session = ref.read(sessionControllerProvider);
      final gate = ref.read(biometricGateProvider);
      final value = session.value;
      final atSplash = state.matchedLocation == Routes.splash;
      final atLogin = state.matchedLocation == Routes.login;

      // Still probing, or the probe failed with a network error. Hold on the splash,
      // which owns the retry — bouncing to login here would log out every user who
      // opened the app with no signal, despite a 7-day session.
      if (session.isLoading || session.hasError || value is SessionUnknown) {
        return atSplash ? null : Routes.splash;
      }

      if (value is SessionSignedOut) {
        // Onboarding is the front door for a signed-out user, not login: most people
        // arriving here have a tag and no password yet, and sending them to a password
        // form they cannot fill is a dead end. Every screen in the setup flow is allowed
        // through, or the redirect would bounce them back mid-flow.
        const openToSignedOut = {
          Routes.login,
          Routes.onboarding,
          Routes.phoneEntry,
          Routes.otp,
          Routes.setPassword,
          // Reachable only from the login screen, which is itself signed-out — so it has to
          // be in this list or the guard bounces the user out of the flow they just began.
          Routes.forgotPassword,
        };
        return openToSignedOut.contains(state.matchedLocation)
            ? null
            : Routes.onboarding;
      }

      if (value is SessionSignedIn) {
        // The gate is checked BEFORE anything else here, and that order is the whole
        // point: the session is valid, so without this the cold-start probe walks
        // straight into the dashboard and the lock never gets a chance to apply.
        //
        // While the gate itself is still resolving, treat it as locked. Guessing
        // "unlocked" would flash the dashboard for a frame before the prompt — showing
        // a balance to whoever is holding the phone, which is exactly what the gate is
        // meant to prevent.
        final locked = gate.value?.isLocked ?? gate.isLoading;
        final atUnlock = state.matchedLocation == Routes.unlock;
        if (locked) return atUnlock ? null : Routes.unlock;
        if (atSplash || atLogin || atUnlock) return Routes.dashboard;
        return null;
      }

      return null;
    },
    routes: [
      GoRoute(
        path: Routes.splash,
        builder: (context, state) => const SplashScreen(),
      ),
      GoRoute(
        path: Routes.unlock,
        parentNavigatorKey: _rootKey,
        builder: (context, state) => const UnlockScreen(),
      ),
      GoRoute(
        path: Routes.onboarding,
        parentNavigatorKey: _rootKey,
        builder: (context, state) => const OnboardingScreen(),
      ),
      GoRoute(
        path: Routes.phoneEntry,
        parentNavigatorKey: _rootKey,
        pageBuilder: (context, state) =>
            _clayPage(state, const PhoneEntryScreen()),
      ),
      GoRoute(
        path: Routes.forgotPassword,
        parentNavigatorKey: _rootKey,
        pageBuilder: (context, state) => _clayPage(
          state,
          const PhoneEntryScreen(purpose: OtpPurpose.passwordReset),
        ),
      ),
      GoRoute(
        path: Routes.otp,
        parentNavigatorKey: _rootKey,
        pageBuilder: (context, state) => _clayPage(state, const OtpScreen()),
      ),
      GoRoute(
        path: Routes.setPassword,
        parentNavigatorKey: _rootKey,
        // Same reason as login, and more of it: by the time a password is set the user is
        // three imperative pushes deep (phone -> otp -> password). `go` discards all of
        // them; popping would leave the OTP screen underneath the dashboard.
        pageBuilder: (context, state) => _clayPage(
          state,
          const SignedInExit(child: SetPasswordScreen()),
        ),
      ),
      GoRoute(
        path: Routes.login,
        // Wrapped because this screen is reached with `context.push`, and go_router leaves an
        // imperatively pushed page on top of whatever `redirect` decides. Without this the
        // redirect below puts the dashboard underneath and the login form stays visible —
        // login looks like it did nothing until the app is restarted.
        builder: (context, state) => const SignedInExit(child: LoginScreen()),
      ),

      // The four bottom-nav tabs keep their own navigation stacks inside the shell,
      // so switching tabs does not discard where you were in the other one.
      StatefulShellRoute.indexedStack(
        parentNavigatorKey: _rootKey,
        builder: (context, state, navigationShell) =>
            AppShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(
            navigatorKey: _shellKey,
            routes: [
              GoRoute(
                path: Routes.dashboard,
                builder: (context, state) => const DashboardScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.tags,
                builder: (context, state) => const TagsScreen(),
                routes: [
                  GoRoute(
                    path: Routes.tagDetail,
                    builder: (context, state) => TagDetailScreen(
                      tagSerial: state.pathParameters['serial'] ?? '',
                    ),
                  ),
                ],
              ),
            ],
          ),
          // Plazas — the prominent centre tab. Replaces the design spec's "Scan QR":
          // M-Tag is RFID, so there is nothing for a consumer to scan and no endpoint that
          // would accept a scan. This branch shows real plaza and fare data instead.
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.plazas,
                pageBuilder: (context, state) =>
                    const NoTransitionPage(child: PlazasScreen()),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.activity,
                builder: (context, state) => const TransactionsScreen(),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: Routes.profile,
                builder: (context, state) => const ProfileScreen(),
              ),
            ],
          ),
        ],
      ),

      // Pushed over the shell: these are destinations you come back FROM, not places
      // you live. Top Up in particular must not be a nav tab — see ClayBottomNav.
      GoRoute(
        path: Routes.topup,
        parentNavigatorKey: _rootKey,
        pageBuilder: (context, state) => _clayPage(
          state,
          TopupScreen(
            initialAccountId: int.tryParse(
              state.uri.queryParameters['account'] ?? '',
            ),
          ),
        ),
      ),
      GoRoute(
        path: Routes.vehicles,
        parentNavigatorKey: _rootKey,
        pageBuilder: (context, state) =>
            _clayPage(state, const VehiclesScreen()),
      ),
      GoRoute(
        path: Routes.vehicleDetail,
        parentNavigatorKey: _rootKey,
        pageBuilder: (context, state) => _clayPage(
          state,
          VehicleDetailScreen(
            vehicleId: int.tryParse(state.pathParameters['id'] ?? '') ?? 0,
          ),
        ),
      ),
      GoRoute(
        path: Routes.trips,
        parentNavigatorKey: _rootKey,
        pageBuilder: (context, state) => _clayPage(
          state,
          TripsScreen(
            vehicleId:
                int.tryParse(state.pathParameters['vehicleId'] ?? '') ?? 0,
          ),
        ),
      ),
      GoRoute(
        path: Routes.fares,
        parentNavigatorKey: _rootKey,
        pageBuilder: (context, state) => _clayPage(state, const FaresScreen()),
      ),
    ],
  );
});

/// Wraps a pushed screen in the app's page transition.
///
/// A short fade with a small upward slide, rather than the platform's horizontal push.
/// Every screen that uses this (Top Up, Vehicles, Vehicle detail, Trips, Fares) is a
/// DETAIL of what the user was already looking at — a slide-over implies travelling
/// somewhere else, which is the wrong story for drilling into your own tag.
///
/// The tabs inside the shell deliberately do NOT use it: switching tabs should be instant,
/// and animating it would put a transition between two things the user is comparing.
CustomTransitionPage<void> _clayPage(GoRouterState state, Widget child) {
  return CustomTransitionPage<void>(
    key: state.pageKey,
    transitionDuration: ClayMotion.page,
    reverseTransitionDuration: ClayMotion.page,
    child: child,
    transitionsBuilder: clayPageTransition,
  );
}
