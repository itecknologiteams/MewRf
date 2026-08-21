import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/errors/app_failure.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/user.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/features/notifications/presentation/push_controller.dart';

/// Where the session stands. The router's single input.
sealed class SessionState {
  const SessionState();
}

/// Cold start: the jar is open but `/auth/me/` has not answered. The splash screen
/// holds here.
class SessionUnknown extends SessionState {
  const SessionUnknown();
}

class SessionSignedOut extends SessionState {
  const SessionSignedOut({this.reason});

  /// Set when the user was PUSHED out — a refresh that failed, a blacklisted token —
  /// as opposed to tapping Log Out. The login screen says which, because "you were
  /// signed out" with no explanation reads as a bug.
  final AppFailure? reason;
}

class SessionSignedIn extends SessionState {
  const SessionSignedIn(this.user);

  final AppUser user;

  /// The app is a consumer wallet. An operator or admin CAN authenticate with these
  /// credentials, and the honest response is to say so and point at the portal —
  /// not to show them a dashboard that will 403 on half its calls, and not to
  /// silently refuse a valid login.
  bool get isStaffAccount => !user.role.isConsumer;
}

/// Owns the session and nothing else.
///
/// Deliberately not merged with the dashboard controller: the router redirects on
/// this state, so anything that makes it rebuild causes a navigation. Keeping it to
/// "who is signed in" means a failed balance refresh cannot bounce the user to the
/// login screen.
class SessionController extends AsyncNotifier<SessionState> {
  StreamSubscription<void>? _expiry;

  @override
  Future<SessionState> build() async {
    final client = ref.watch(apiClientProvider);

    // The refresh interceptor fires this when a refresh fails, which is the only
    // path by which a user is signed out without asking.
    unawaited(_expiry?.cancel());
    _expiry = client.onSessionExpired.listen((_) {
      state = const AsyncValue.data(
        SessionSignedOut(
          reason: UnauthorisedFailure(message: 'session expired'),
        ),
      );
    });
    ref.onDispose(() => _expiry?.cancel());

    return _probe();
  }

  /// The cold-start probe.
  ///
  /// `GET /auth/me/` is the only reliable check. A cookie in the jar proves nothing:
  /// `CookieJWTAuthentication` treats an unusable access-token cookie as anonymous
  /// rather than raising, so a stale jar yields a 401 from the permission layer —
  /// and by the time that surfaces here, the refresh interceptor has already tried
  /// once to fix it. So a 401 at this point means the session is genuinely over.
  Future<SessionState> _probe() async {
    final auth = ref.read(authRepositoryProvider);
    try {
      return SessionSignedIn(await auth.me());
    } on UnauthorisedFailure {
      return const SessionSignedOut();
    } on AppFailure {
      // A network failure is NOT a signed-out state. Treating it as one would log
      // users out every time they open the app in a basement, and their session is
      // good for 7 days. Reported as an error so the splash can offer Retry while
      // keeping the jar intact.
      rethrow;
    }
  }

  Future<void> signIn({
    required String phone,
    required String password,
    bool rememberPhone = true,
  }) async {
    final auth = ref.read(authRepositoryProvider);
    final result = await auth.login(
      phone: phone,
      password: password,
      rememberPhone: rememberPhone,
    );

    // /auth/me/ is re-read rather than trusting the login body: the login response
    // carries no `cnic` or `status`, and the app would otherwise show an empty CNIC
    // on the profile screen until the next cold start.
    try {
      state = AsyncValue.data(SessionSignedIn(await auth.me()));
    } on AppFailure {
      // The login itself succeeded and the cookies are in the jar. Fall back to the
      // login body rather than dropping the user back to the login screen with
      // valid credentials.
      state = AsyncValue.data(
        SessionSignedIn(
          AppUser(
            id: result.userId,
            uuid: result.uuid,
            fullName: result.fullName,
            phone: result.phone,
            role: result.role,
            status: UserStatus.active,
          ),
        ),
      );
    }
  }

  Future<void> signOut() async {
    final auth = ref.read(authRepositoryProvider);

    // BEFORE the state flips and before `logout()` clears the cookies.
    //
    // `/notifications/devices/unregister/` is IsAuthenticated and scopes its delete to
    // `user=request.user`, so once the session is gone the call 401s and the row survives —
    // and the next person to hold this phone keeps receiving the previous owner's balance
    // notifications. FCM hands the same token to whoever installs next, so that is a real
    // handset, not a hypothetical one.
    //
    // Awaited despite the optimistic sign-out below, and it is the one thing here worth
    // waiting for: everything else is recoverable locally, this is not.
    try {
      await ref.read(pushControllerProvider.notifier).releaseForSignOut();
    } on Object {
      // Never block leaving. A user who cannot sign out because a notification token
      // would not delete is worse off than one whose token lingers.
    }

    // Optimistic on purpose, and the one place in this app where that is right: the
    // user asked to leave, so the UI leaves immediately and the server call and
    // cache wipe happen behind it. `logout()` clears the local session regardless of
    // whether the server was reachable.
    state = const AsyncValue.data(SessionSignedOut());
    ref.read(capabilitiesProvider).reset();
    await auth.logout();
  }

  /// Retry after a network failure on the cold-start probe.
  Future<void> retry() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(_probe);
  }

  /// Refreshes the cached user after a profile edit.
  Future<void> refreshUser() async {
    final current = state.value;
    if (current is! SessionSignedIn) return;
    try {
      state = AsyncValue.data(
        SessionSignedIn(await ref.read(authRepositoryProvider).me()),
      );
    } on AppFailure {
      // Keep showing the user we have; a failed refresh is not a reason to blank the
      // profile screen.
    }
  }
}

final sessionControllerProvider =
    AsyncNotifierProvider<SessionController, SessionState>(
      SessionController.new,
    );

/// The signed-in user, or null. What most screens actually want.
final currentUserProvider = Provider<AppUser?>((ref) {
  final session = ref.watch(sessionControllerProvider).value;
  return session is SessionSignedIn ? session.user : null;
});
