import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/dashboard/presentation/wallet_controller.dart';
import 'package:mtag_user_app/features/trips/presentation/trips_controller.dart';
import 'package:mtag_user_app/features/trips/presentation/widgets/trip_card.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

class TripsScreen extends ConsumerStatefulWidget {
  const TripsScreen({required this.vehicleId, super.key});

  final int vehicleId;

  @override
  ConsumerState<TripsScreen> createState() => _TripsScreenState();
}

class _TripsScreenState extends ConsumerState<TripsScreen> {
  final _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController
      ..removeListener(_onScroll)
      ..dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_scrollController.hasClients) return;
    final position = _scrollController.position;
    if (position.pixels >= position.maxScrollExtent - 600) {
      ref.read(tripsControllerProvider(widget.vehicleId).notifier).loadMore();
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final async = ref.watch(tripsControllerProvider(widget.vehicleId));
    final vehicle = ref.watch(vehicleByIdProvider(widget.vehicleId));

    return ClayScaffold(
      title: l10n.tripsTitle,
      subtitle: vehicle?.plateNumber,
      showBack: true,
      body: async.when(
        loading: () => ListView(
          physics: const NeverScrollableScrollPhysics(),
          children: const [
            ClaySkeletonCard(lines: 4, height: 200),
            SizedBox(height: ClaySpace.cardGap),
            ClaySkeletonCard(lines: 4, height: 200),
          ],
        ),
        error: (error, _) => ClayErrorState(
          message: describeError(error, l10n),
          retryLabel: l10n.actionRetry,
          onRetry: () => ref
              .read(tripsControllerProvider(widget.vehicleId).notifier)
              .refresh(),
        ),
        data: (page) {
          if (page.items.isEmpty) {
            return ClayEmptyState(
              icon: Icons.route_rounded,
              title: l10n.tripsEmptyTitle,
              message: l10n.tripsEmptyBody,
            );
          }

          return RefreshIndicator(
            onRefresh: () => ref
                .read(tripsControllerProvider(widget.vehicleId).notifier)
                .refresh(),
            child: ListView.separated(
              controller: _scrollController,
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.only(bottom: ClaySpace.xxl),
              // +1 for the "charges can arrive late" note, which belongs at the top of
              // a trip list for the same reason it does on the transaction list.
              itemCount: page.items.length + 1,
              separatorBuilder: (_, _) =>
                  const SizedBox(height: ClaySpace.cardGap),
              itemBuilder: (context, index) {
                if (index == 0) {
                  return Text(
                    l10n.transactionsNotRealtime,
                    style: Theme.of(context).textTheme.bodySmall,
                  );
                }
                return TripCard(trip: page.items[index - 1]);
              },
            ),
          );
        },
      ),
    );
  }
}
