import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/dashboard/presentation/wallet_controller.dart';
import 'package:mtag_user_app/features/notifications/presentation/push_controller.dart';
import 'package:mtag_user_app/features/transactions/presentation/transactions_controller.dart';
import 'package:mtag_user_app/features/trips/presentation/my_trips_controller.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// The five-tab shell: Home · Tags · Plazas · Activity · Profile.
///
/// Top Up is NOT a tab. It is a prominent CTA on Home and Tag detail, because it is
/// something you do to a specific tag rather than a place you go — a nav slot would
/// leave the user on a Top Up screen asking "which of my three tags?".
///
/// It is also where push lands, for two reasons: it is mounted for the whole signed-in
/// session, and it owns a `ScaffoldMessenger` context that can show a banner.
class AppShell extends ConsumerStatefulWidget {
  const AppShell({required this.navigationShell, super.key});

  final StatefulNavigationShell navigationShell;

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  StreamSubscription<PushEvent>? _events;
  StreamSubscription<PushEvent>? _taps;
  bool _handledInitialTap = false;

  @override
  void initState() {
    super.initState();
    // Post-frame: the push controller may still be building, and navigating during the
    // first build of the route that hosts the navigator throws.
    WidgetsBinding.instance.addPostFrameCallback((_) => _attach());
  }

  @override
  void dispose() {
    _events?.cancel();
    _taps?.cancel();
    super.dispose();
  }

  void _attach() {
    if (!mounted) return;
    final controller = ref.read(pushControllerProvider.notifier);

    _events ??= controller.events.listen(_onForeground);
    _taps ??= controller.taps.listen(_onTap);

    if (!_handledInitialTap) {
      _handledInitialTap = true;
      // A cold start FROM a notification tap. The tap predates every listener, so it has
      // to be pulled rather than awaited.
      controller.initialTap().then((event) {
        if (event != null && mounted) _onTap(event);
      });
    }
  }

  /// A push that arrived while the app was open and in front of the user.
  ///
  /// Deliberately does NOT raise a system notification. The OS tray is for things the user
  /// is not currently looking at; an app in the foreground should update itself and say so
  /// in place. So the balance is refetched and a banner explains why the number moved.
  ///
  /// The refresh is the important half. Without it the user reads "Toll paid · Rs. 120" in a
  /// notification while the dashboard behind it still shows the old balance, and has to
  /// pull-to-refresh to reconcile two numbers the app already knew were different.
  void _onForeground(PushEvent event) {
    if (!mounted) return;

    if (event.affectsBalance) {
      // The server is the only authority on a balance; this asks it again rather than
      // applying the amount from the notification, which would be a client-side ledger.
      ref
        ..invalidate(walletControllerProvider)
        ..invalidate(transactionsControllerProvider)
        // A toll charge is also a completed trip, so the journey list is stale too.
        ..invalidate(myTripsControllerProvider);
    }

    final message = event.title.isEmpty
        ? AppL10n.of(context).pushBalanceUpdated
        : [event.title, event.body].where((s) => s.isNotEmpty).join(' · ');

    showClaySnack(
      context,
      message: message,
      icon: Icons.notifications_active_rounded,
      actionLabel: event.route == null
          ? null
          : AppL10n.of(context).actionView,
      onAction: event.route == null ? null : () => _navigate(event.route!),
    );
  }

  void _onTap(PushEvent event) {
    final route = event.route;
    if (route == null || !mounted) return;
    _navigate(route);
  }

  void _navigate(String route) {
    if (!mounted) return;
    // The route string comes from the SERVER (`/activity?account=12`), so an unknown path
    // from a newer backend must not crash the app. go_router throws on an unmatched
    // location, which for a notification tap would mean the app dies as it opens.
    try {
      GoRouter.of(context).go(route);
    } on Object {
      // Better to land on the dashboard than to die on the doorstep.
      GoRouter.of(context).go('/');
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;

    // Watched, not just read: the controller is what registers the device token, and a
    // provider nobody watches is never built. Without this line push would be wired
    // end to end and never initialise.
    ref.watch(pushControllerProvider);

    return Scaffold(
      backgroundColor: palette.base,
      // Painted once here, not per screen: the glow is what the glass panels blur
      // against, and re-creating it per tab would flicker on every switch.
      body: ClayAmbient(child: widget.navigationShell),
      bottomNavigationBar: ClayBottomNav(
        currentIndex: widget.navigationShell.currentIndex,
        prominentIndex: 2,
        onTap: (index) => widget.navigationShell.goBranch(
          index,
          // Tapping the tab you are already on pops back to that branch's root —
          // the standard gesture for "take me back to the top of this section".
          initialLocation: index == widget.navigationShell.currentIndex,
        ),
        items: [
          // Outline when unselected, filled when selected — so the current tab is legible
          // by icon weight alone, not only by its colour.
          ClayNavItem(
            icon: Icons.home_outlined,
            activeIcon: Icons.home_rounded,
            label: l10n.navHome,
          ),
          ClayNavItem(
            icon: Icons.sensors_outlined,
            activeIcon: Icons.sensors_rounded,
            label: l10n.navTags,
          ),
          // Index 2 — the prominent centre action. Not a fifth peer tab: it is rendered
          // as a raised orange circle overhanging the bar, which is what makes it read as
          // the primary destination.
          ClayNavItem(
            icon: Icons.location_on_outlined,
            activeIcon: Icons.location_on_rounded,
            label: l10n.navPlazas,
          ),
          ClayNavItem(
            icon: Icons.receipt_long_outlined,
            activeIcon: Icons.receipt_long_rounded,
            label: l10n.navActivity,
          ),
          ClayNavItem(
            icon: Icons.person_outline_rounded,
            activeIcon: Icons.person_rounded,
            label: l10n.navProfile,
          ),
        ],
      ),
    );
  }
}
