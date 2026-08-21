import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/dashboard/presentation/wallet_controller.dart';
import 'package:mtag_user_app/features/transactions/presentation/transactions_controller.dart';
import 'package:mtag_user_app/features/transactions/presentation/widgets/transaction_row.dart';
import 'package:mtag_user_app/features/trips/presentation/my_trips_controller.dart';
import 'package:mtag_user_app/features/trips/presentation/widgets/trip_card.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// The two halves of Activity.
///
/// Trips live here rather than only under Vehicles > detail > View all, which is where they
/// used to be: four taps down, behind a tile labelled for vehicles. A toll charge produces
/// BOTH a transaction and a trip, and they answer different questions — "what did it cost"
/// versus "where did I actually drive" — so the money list alone left the journey history
/// effectively unreachable.
enum ActivitySegment { payments, trips }

class TransactionsScreen extends ConsumerStatefulWidget {
  const TransactionsScreen({super.key});

  @override
  ConsumerState<TransactionsScreen> createState() => _TransactionsScreenState();
}

class _TransactionsScreenState extends ConsumerState<TransactionsScreen> {
  final _scrollController = ScrollController();
  // A SECOND controller, not one shared between the panes. One controller attached to two
  // scroll views throws the moment both exist, and reusing it across a switch would carry
  // the payments offset onto a trip list of a different length.
  final _tripsScrollController = ScrollController();

  ActivitySegment _segment = ActivitySegment.payments;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _tripsScrollController.addListener(_onTripsScroll);
  }

  @override
  void dispose() {
    _scrollController
      ..removeListener(_onScroll)
      ..dispose();
    _tripsScrollController
      ..removeListener(_onTripsScroll)
      ..dispose();
    super.dispose();
  }

  void _onTripsScroll() {
    if (!_tripsScrollController.hasClients) return;
    final position = _tripsScrollController.position;
    if (position.pixels >= position.maxScrollExtent - 600) {
      ref.read(myTripsControllerProvider.notifier).loadMore();
    }
  }

  void _refreshActive() {
    switch (_segment) {
      case ActivitySegment.payments:
        ref.read(transactionsControllerProvider.notifier).refresh();
      case ActivitySegment.trips:
        ref.read(myTripsControllerProvider.notifier).refresh();
    }
  }

  /// Prefetches 600px before the end, so the next page is usually there by the time
  /// the user reaches it rather than stopping them at a spinner.
  void _onScroll() {
    if (!_scrollController.hasClients) return;
    final position = _scrollController.position;
    if (position.pixels >= position.maxScrollExtent - 600) {
      ref.read(transactionsControllerProvider.notifier).loadMore();
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final async = ref.watch(transactionsControllerProvider);
    final wallet = ref.watch(walletControllerProvider).value;
    final multipleAccounts = (wallet?.vehicles.length ?? 0) > 1;

    return Scaffold(
      backgroundColor: palette.base,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(
                ClaySpace.gutter,
                ClaySpace.lg,
                ClaySpace.gutter,
                ClaySpace.md,
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      l10n.transactionsTitle,
                      style: Theme.of(context).textTheme.headlineMedium,
                    ),
                  ),
                  ClayIconButton(
                    icon: Icons.refresh_rounded,
                    semanticLabel: l10n.actionRefresh,
                    // Whichever pane is showing. Refreshing the hidden list while the
                    // user watches an unchanged one reads as a broken button.
                    onPressed: _refreshActive,
                  ),
                ],
              ),
            ),

            _SegmentToggle(
              segment: _segment,
              onChanged: (segment) => setState(() => _segment = segment),
            ),

            if (_segment == ActivitySegment.payments) ...[
              _FilterBar(
                filter: async.value?.filter ?? TransactionFilter.all,
                onChanged: (filter) => ref
                    .read(transactionsControllerProvider.notifier)
                    .setFilter(filter),
              ),

              if (multipleAccounts)
                _AccountBar(
                  selected: async.value?.selectedAccountId,
                  onChanged: (accountId) => ref
                      .read(transactionsControllerProvider.notifier)
                      .selectAccount(accountId),
                ),

              Expanded(
                child: async.when(
                  loading: () => const _TransactionsSkeleton(),
                  error: (error, _) => Padding(
                    padding: const EdgeInsets.all(ClaySpace.gutter),
                    child: ClayErrorState(
                      message: describeError(error, l10n),
                      retryLabel: l10n.actionRetry,
                      onRetry: () => ref
                          .read(transactionsControllerProvider.notifier)
                          .refresh(),
                    ),
                  ),
                  data: (state) => RefreshIndicator(
                    onRefresh: () => ref
                        .read(transactionsControllerProvider.notifier)
                        .refresh(),
                    color: palette.primary,
                    backgroundColor: palette.surface,
                    child: state.isEmpty
                        ? _EmptyList(
                            filtered: state.filter != TransactionFilter.all,
                          )
                        : _TransactionList(
                            state: state,
                            controller: _scrollController,
                            showPlate:
                                multipleAccounts &&
                                state.selectedAccountId == null,
                          ),
                  ),
                ),
              ),
            ] else
              Expanded(
                child: _TripsPane(
                  controller: _tripsScrollController,
                  // A holder with two cars needs to know WHICH one made the trip; with one
                  // car the plate on every row is noise.
                  showPlate: multipleAccounts,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _TransactionList extends StatelessWidget {
  const _TransactionList({
    required this.state,
    required this.controller,
    required this.showPlate,
  });

  final TransactionsState state;
  final ScrollController controller;
  final bool showPlate;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);

    return CustomScrollView(
      controller: controller,
      physics: const AlwaysScrollableScrollPhysics(),
      slivers: [
        SliverPadding(
          padding: const EdgeInsets.symmetric(horizontal: ClaySpace.gutter),
          sliver: SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.only(bottom: ClaySpace.md),
              child: Text(
                l10n.transactionsNotRealtime,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ),
        ),

        // Two slivers per day, appended DIRECTLY to the CustomScrollView.
        //
        // Not wrapped in a SliverMainAxisGroup, which is where they started: the group
        // hands its children a reduced `remainingPaintExtent`, but a pinned
        // SliverPersistentHeader reports `layoutExtent = minExtent` unconditionally and
        // does not clamp to it. The last group in a viewport therefore claimed 44px of
        // layout against 41px of paint, and Flutter threw
        // "SliverGeometry is not valid: layoutExtent exceeds paintExtent" — several times
        // per frame, each followed by null-check failures as the unsized render objects
        // were painted. Nothing appeared on screen to say so.
        //
        // Emitted flat, consecutive pinned headers give exactly the sticky-day behaviour
        // the group was there for anyway: each one holds the top until the next pushes it
        // off. The padding just moves onto each sliver individually.
        for (final day in state.days) ...[
          SliverPadding(
            padding: const EdgeInsets.symmetric(horizontal: ClaySpace.gutter),
            sliver: SliverPersistentHeader(
              pinned: true,
              delegate: _DayHeaderDelegate(
                day: day.day,
                // Measured from the current text scale rather than hardcoded — see the
                // delegate.
                extent: _DayHeaderDelegate.extentFor(context),
              ),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsets.symmetric(horizontal: ClaySpace.gutter),
            sliver: SliverToBoxAdapter(
              // One clay card PER ROW, stacked with a small gap — the design spec's
              // assignment for transaction history. Individually wrapped rather than rows
              // inside one shared card, because the point of clay here is that each entry
              // reads as its own soft object you could pick up.
              child: Column(
                children: [
                  for (final transaction in day.transactions)
                    Padding(
                      padding: const EdgeInsets.only(bottom: ClaySpace.sm),
                      child: ClayCard(
                        style: ClayDepthStyle.clay,
                        padding: EdgeInsets.zero,
                        child: TransactionRow(
                          transaction: transaction,
                          showPlate: showPlate,
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],

        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.only(
              top: ClaySpace.xl,
              bottom: ClaySpace.xl,
            ),
            child: Center(
              child: state.isLoadingMore
                  ? const SizedBox(
                      width: 120,
                      child: ClaySkeleton.line(height: 12),
                    )
                  : const SizedBox.shrink(),
            ),
          ),
        ),
      ],
    );
  }
}

class _DayHeaderDelegate extends SliverPersistentHeaderDelegate {
  const _DayHeaderDelegate({required this.day, required this.extent});

  final DateTime day;

  /// The header's height, measured for the current text scale.
  ///
  /// A persistent header's extent is a fixed number that the delegate must state up front,
  /// and it CLIPS rather than growing if the content turns out taller. Hardcoding 44
  /// worked at the default text scale and silently cut the date in half for anyone running
  /// large system text — which is a lot of this user base, since the app is read at arm's
  /// length in a car.
  final double extent;

  /// DayHeader's real height: its vertical padding plus one line of labelMedium.
  ///
  /// Kept next to the widget it measures so the two cannot drift. If DayHeader's padding
  /// or style changes, this is the line to change with it.
  static double extentFor(BuildContext context) {
    const verticalPadding = ClaySpace.lg + ClaySpace.sm;
    const fontSize = 13.0;
    const lineHeight = 1.3;
    final scaled = MediaQuery.textScalerOf(context).scale(fontSize);
    return verticalPadding + (scaled * lineHeight).ceilToDouble();
  }

  @override
  double get minExtent => extent;

  @override
  double get maxExtent => extent;

  @override
  Widget build(
    BuildContext context,
    double shrinkOffset,
    bool overlapsContent,
  ) => DayHeader(day: day);

  @override
  bool shouldRebuild(_DayHeaderDelegate old) =>
      old.day != day || old.extent != extent;
}

class _FilterBar extends StatelessWidget {
  const _FilterBar({required this.filter, required this.onChanged});

  final TransactionFilter filter;
  final ValueChanged<TransactionFilter> onChanged;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final labels = {
      TransactionFilter.all: l10n.transactionsFilterAll,
      TransactionFilter.tolls: l10n.transactionsFilterTolls,
      TransactionFilter.topups: l10n.transactionsFilterTopups,
      TransactionFilter.refunds: l10n.transactionsFilterRefunds,
    };

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(
        horizontal: ClaySpace.gutter,
        vertical: ClaySpace.sm,
      ),
      child: Row(
        children: [
          for (final entry in labels.entries) ...[
            ClayFilterChip(
              label: entry.value,
              selected: filter == entry.key,
              onTap: () => onChanged(entry.key),
            ),
            const SizedBox(width: ClaySpace.sm),
          ],
        ],
      ),
    );
  }
}

/// Vehicle selector, shown only to multi-vehicle holders.
///
/// Present because the server paginates per account: viewing "All" merges pages from
/// every account, which is correct but only ordered within what has been fetched.
/// Picking one vehicle gives exact pagination.
class _AccountBar extends ConsumerWidget {
  const _AccountBar({required this.selected, required this.onChanged});

  final int? selected;
  final ValueChanged<int?> onChanged;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppL10n.of(context);
    final wallet = ref.watch(walletControllerProvider).value;
    final vehicles = (wallet?.vehicles ?? const [])
        .where((v) => v.accountId != null)
        .toList(growable: false);

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.only(
        left: ClaySpace.gutter,
        right: ClaySpace.gutter,
        bottom: ClaySpace.sm,
      ),
      child: Row(
        children: [
          ClayFilterChip(
            label: l10n.transactionsFilterAll,
            selected: selected == null,
            onTap: () => onChanged(null),
          ),
          const SizedBox(width: ClaySpace.sm),
          for (final vehicle in vehicles) ...[
            ClayFilterChip(
              label: vehicle.plateNumber,
              selected: selected == vehicle.accountId,
              onTap: () => onChanged(vehicle.accountId),
            ),
            const SizedBox(width: ClaySpace.sm),
          ],
        ],
      ),
    );
  }
}

class _EmptyList extends StatelessWidget {
  const _EmptyList({required this.filtered});

  final bool filtered;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    return ListView(
      children: [
        SizedBox(
          height: MediaQuery.sizeOf(context).height * 0.55,
          child: ClayEmptyState(
            icon: filtered
                ? Icons.filter_alt_off_rounded
                : Icons.receipt_long_rounded,
            title: filtered
                ? l10n.transactionsEmptyFilteredTitle
                : l10n.transactionsEmptyTitle,
            message: filtered
                ? l10n.transactionsEmptyFilteredBody
                : l10n.transactionsEmptyBody,
          ),
        ),
      ],
    );
  }
}

class _TransactionsSkeleton extends StatelessWidget {
  const _TransactionsSkeleton();

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.symmetric(horizontal: ClaySpace.gutter),
    physics: const NeverScrollableScrollPhysics(),
    children: const [
      ClaySkeleton.line(width: 140),
      SizedBox(height: ClaySpace.md),
      ClaySkeletonCard(lines: 4),
      SizedBox(height: ClaySpace.xl),
      ClaySkeleton.line(width: 160),
      SizedBox(height: ClaySpace.md),
      ClaySkeletonCard(),
    ],
  );
}

/// Payments | Trips.
///
/// A two-up segmented control rather than a third nav tab: both halves are the same
/// question ("what has happened on my account") seen through different lenses, and the nav
/// bar already carries its maximum of five.
class _SegmentToggle extends StatelessWidget {
  const _SegmentToggle({required this.segment, required this.onChanged});

  final ActivitySegment segment;
  final ValueChanged<ActivitySegment> onChanged;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;

    final labels = {
      ActivitySegment.payments: (
        l10n.activitySegmentPayments,
        Icons.receipt_long_rounded,
      ),
      ActivitySegment.trips: (l10n.activitySegmentTrips, Icons.route_rounded),
    };

    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: ClaySpace.gutter,
        vertical: ClaySpace.sm,
      ),
      child: ClaySurface(
        radius: ClayRadius.pill,
        // A groove the selected pill sits IN, so the control reads as one track with a
        // moving thumb rather than two buttons that happen to touch.
        style: ClayDepthStyle.pressed,
        depth: ClayElevation.nested,
        padding: const EdgeInsets.all(4),
        child: Row(
          children: [
            for (final entry in labels.entries)
              Expanded(
                child: _SegmentButton(
                  label: entry.value.$1,
                  icon: entry.value.$2,
                  selected: segment == entry.key,
                  palette: palette,
                  onTap: () => onChanged(entry.key),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _SegmentButton extends StatelessWidget {
  const _SegmentButton({
    required this.label,
    required this.icon,
    required this.selected,
    required this.palette,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final ClayPalette palette;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Semantics(
      button: true,
      selected: selected,
      child: ClayPressable(
        onTap: onTap,
        child: AnimatedContainer(
          duration: clayDuration(context, const Duration(milliseconds: 180)),
          curve: Curves.easeOut,
          padding: const EdgeInsets.symmetric(vertical: ClaySpace.sm + 2),
          decoration: BoxDecoration(
            color: selected ? palette.primary : Colors.transparent,
            borderRadius: BorderRadius.circular(ClayRadius.pill),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 17,
                // Black on orange, matching every other primary surface in the app —
                // white on #FF8500 is 2.4:1 and fails AA outright.
                color: selected ? palette.onPrimary : palette.textMuted,
              ),
              const SizedBox(width: ClaySpace.sm),
              Flexible(
                child: Text(
                  label,
                  style: textTheme.labelLarge?.copyWith(
                    color: selected ? palette.onPrimary : palette.textMuted,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The Trips half of Activity.
class _TripsPane extends ConsumerWidget {
  const _TripsPane({required this.controller, required this.showPlate});

  final ScrollController controller;
  final bool showPlate;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final async = ref.watch(myTripsControllerProvider);

    return Column(
      children: [
        _TripFilterBar(
          filter: async.value?.filter ?? TripFilter.all,
          onChanged: (filter) =>
              ref.read(myTripsControllerProvider.notifier).setFilter(filter),
        ),
        Expanded(
          child: async.when(
            loading: () => const _TransactionsSkeleton(),
            error: (error, _) => Padding(
              padding: const EdgeInsets.all(ClaySpace.gutter),
              child: ClayErrorState(
                message: describeError(error, l10n),
                retryLabel: l10n.actionRetry,
                onRetry: () =>
                    ref.read(myTripsControllerProvider.notifier).refresh(),
              ),
            ),
            data: (state) => RefreshIndicator(
              onRefresh: () =>
                  ref.read(myTripsControllerProvider.notifier).refresh(),
              color: palette.primary,
              backgroundColor: palette.surface,
              child: state.isEmpty
                  ? ListView(
                      // Scrollable even when empty, or pull-to-refresh has nothing to
                      // grab and the only way out of an empty list is the header button.
                      physics: const AlwaysScrollableScrollPhysics(),
                      children: [
                        const SizedBox(height: ClaySpace.xxl),
                        ClayEmptyState(
                          icon: Icons.route_rounded,
                          title: state.filter == TripFilter.all
                              ? l10n.tripsEmptyTitle
                              : l10n.transactionsEmptyFilteredTitle,
                          message: state.filter == TripFilter.all
                              ? l10n.tripsEmptyBody
                              : l10n.transactionsEmptyFilteredBody,
                        ),
                      ],
                    )
                  : _TripsList(
                      state: state,
                      controller: controller,
                      showPlate: showPlate,
                    ),
            ),
          ),
        ),
      ],
    );
  }
}

class _TripsList extends StatelessWidget {
  const _TripsList({
    required this.state,
    required this.controller,
    required this.showPlate,
  });

  final MyTripsState state;
  final ScrollController controller;
  final bool showPlate;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final textTheme = Theme.of(context).textTheme;

    return ListView.separated(
      controller: controller,
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(
        ClaySpace.gutter,
        ClaySpace.sm,
        ClaySpace.gutter,
        ClaySpace.xxl,
      ),
      // One header, one row per trip, and a trailing loader only while a page is in
      // flight.
      itemCount: state.trips.length + 1 + (state.isLoadingMore ? 1 : 0),
      separatorBuilder: (_, _) => const SizedBox(height: ClaySpace.cardGap),
      itemBuilder: (context, index) {
        if (index == 0) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (state.isFromCache) ...[
                ClayBanner(
                  icon: Icons.cloud_off_rounded,
                  title: l10n.tripsStaleNotice,
                ),
                const SizedBox(height: ClaySpace.md),
              ],
              Text(
                l10n.tripsCountLabel(state.totalCount),
                style: textTheme.bodySmall,
              ),
              const SizedBox(height: ClaySpace.xs),
              Text(l10n.transactionsNotRealtime, style: textTheme.bodySmall),
            ],
          );
        }

        final tripIndex = index - 1;
        if (tripIndex >= state.trips.length) {
          return const Padding(
            padding: EdgeInsets.symmetric(vertical: ClaySpace.lg),
            // Indeterminate: ClayProgressRing takes a real 0..1 value and there is no
            // honest one here — the server does not say how many rows are coming.
            child: Center(
              child: SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(strokeWidth: 2.2),
              ),
            ),
          );
        }

        return TripCard(trip: state.trips[tripIndex], showPlate: showPlate);
      },
    );
  }
}

class _TripFilterBar extends StatelessWidget {
  const _TripFilterBar({required this.filter, required this.onChanged});

  final TripFilter filter;
  final ValueChanged<TripFilter> onChanged;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final labels = {
      TripFilter.all: l10n.tripsFilterAll,
      TripFilter.live: l10n.tripsFilterLive,
      TripFilter.completed: l10n.tripsFilterCompleted,
    };

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(
        horizontal: ClaySpace.gutter,
        vertical: ClaySpace.sm,
      ),
      child: Row(
        children: [
          for (final entry in labels.entries) ...[
            ClayFilterChip(
              label: entry.value,
              selected: filter == entry.key,
              onTap: () => onChanged(entry.key),
            ),
            const SizedBox(width: ClaySpace.sm),
          ],
        ],
      ),
    );
  }
}
