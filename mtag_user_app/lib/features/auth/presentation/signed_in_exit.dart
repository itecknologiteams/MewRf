import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mtag_user_app/core/router/app_router.dart';
import 'package:mtag_user_app/features/auth/presentation/session_controller.dart';

/// Leaves an auth screen once a session exists.
///
/// ## The bug this exists for
///
/// Signing in appeared to do nothing. The credentials were accepted, the cookies landed, the
/// session state flipped to `SessionSignedIn` — and the login form stayed on screen. Closing
/// and reopening the app then went straight to the dashboard, which is the tell: the jar was
/// correct all along, so the next cold start routed properly while the live change did not.
///
/// The router was not at fault. Its `redirect` correctly returns [Routes.dashboard] for a
/// signed-in user sitting on [Routes.login], and `refreshListenable` does re-run it. But the
/// login screen is reached with `context.push`, and go_router's redirect governs the
/// DECLARATIVE location — an imperatively pushed page is left on top of whatever the
/// redirect decides. So the dashboard was placed underneath and the pushed login page went on
/// covering it.
///
/// `go` is the fix rather than `pop`: it replaces the location AND discards the imperative
/// stack, so no half-finished setup screen survives underneath. Popping would only remove one
/// page, which is wrong for the setup flow — phone → otp → password is three pushes deep by
/// the time the password is set.
///
/// It sends everyone to [Routes.dashboard] and lets the router take it from there. A user
/// with the biometric lock on is then redirected to [Routes.unlock] by the same `redirect`
/// that guards a cold start, so the gate is not bypassed by this shortcut.
class SignedInExit extends ConsumerWidget {
  const SignedInExit({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // `listen`, not `watch`: this must not rebuild the wrapped screen on every session
    // change — the login form would lose its half-typed password. The callback runs after
    // the frame, so navigating from it is safe.
    ref.listen(sessionControllerProvider, (previous, next) {
      if (next.value is! SessionSignedIn) return;
      if (!context.mounted) return;
      context.go(Routes.dashboard);
    });

    return child;
  }
}
