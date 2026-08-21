import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mtag_user_app/core/models/toll.dart';
import 'package:mtag_user_app/core/router/app_router.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/core/utils/money.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/fares/presentation/fares_controller.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Plazas — every toll plaza on the expressway, and what a trip to each one costs.
///
/// This replaces the design spec's "Scan QR" tab. M-Tag is RFID: a gantry reads the tag and
/// the server charges the account, so there is nothing for a consumer to scan and no
/// endpoint that would accept a scan. This tab is built entirely from data that already
/// exists — `/tolls/plazas/` and the directional fare matrix from `/tolls/rates/`.
///
/// **Fares are directional.** Choosing an origin shows the cost FROM there TO each plaza;
/// the reverse is a separate row in `fare_matrix` and can legitimately differ. Nothing here
/// falls back to the opposite direction when a row is absent — quoting a price the driver
/// will not be charged is worse than saying it is unavailable.
class PlazasScreen extends ConsumerWidget {
  const PlazasScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;
    final async = ref.watch(faresControllerProvider);

    return Scaffold(
      // Transparent: the shell paints the ambient glow behind every tab.
      backgroundColor: Colors.transparent,
      body: SafeArea(
        bottom: false,
        child: async.when(
          loading: () => const _PlazasSkeleton(),
          error: (error, _) => Padding(
            padding: const EdgeInsets.all(ClaySpace.gutter),
            child: ClayErrorState(
              message: describeError(error, l10n),
              retryLabel: l10n.actionRetry,
              onRetry: () =>
                  ref.read(faresControllerProvider.notifier).refresh(),
            ),
          ),
          data: (state) => RefreshIndicator(
            onRefresh: () =>
                ref.read(faresControllerProvider.notifier).refresh(),
            color: palette.primary,
            backgroundColor: palette.surface,
            child: _PlazaList(state: state, l10n: l10n, textTheme: textTheme),
          ),
        ),
      ),
    );
  }
}

class _PlazaList extends ConsumerWidget {
  const _PlazaList({
    required this.state,
    required this.l10n,
    required this.textTheme,
  });

  final FaresState state;
  final AppL10n l10n;
  final TextTheme textTheme;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final origin = state.fromPlaza;

    return ListView(
      padding: const EdgeInsets.only(
        left: ClaySpace.gutter,
        right: ClaySpace.gutter,
        top: ClaySpace.lg,
        // Clears the prominent centre button, which overhangs the bar's top edge.
        bottom: ClaySpace.xxl * 2,
      ),
      children: [
        Text(l10n.plazasTitle, style: textTheme.headlineMedium),
        const SizedBox(height: ClaySpace.xs),
        Text(l10n.plazasSubtitle, style: textTheme.bodySmall),
        const SizedBox(height: ClaySpace.lg),

        // Until an origin is chosen there is no fare to show, so the list renders as a
        // plain directory rather than inventing a default origin the driver never picked.
        ClayCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(l10n.plazasFromLabel, style: textTheme.labelSmall),
              const SizedBox(height: ClaySpace.sm),
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    for (final plaza in state.plazas)
                      Padding(
                        padding: const EdgeInsets.only(right: ClaySpace.sm),
                        child: ClayFilterChip(
                          // Zero-padded operator number. Plazas 105 and 106 are BOTH named
                          // "Quaidabad Interchange", so the id is the only thing that
                          // distinguishes them.
                          label: '${plaza.displayId}  ${plaza.name}',
                          selected: plaza.id == state.fromPlazaId,
                          onTap: () => ref
                              .read(faresControllerProvider.notifier)
                              .setFrom(plaza.id),
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: ClaySpace.lg),
        Text(
          origin == null
              ? l10n.plazasAllPlazas
              : l10n.plazasFaresFrom(origin.name),
          style: textTheme.titleMedium,
        ),
        const SizedBox(height: ClaySpace.md),

        for (final (index, plaza) in state.plazas.indexed)
          ClayEntrance(
            index: index,
            child: Padding(
              padding: const EdgeInsets.only(bottom: ClaySpace.md),
              child: _PlazaRow(
                plaza: plaza,
                isOrigin: plaza.id == state.fromPlazaId,
                fare: _fareTo(plaza),
                onTap: () => ref
                    .read(faresControllerProvider.notifier)
                    .setFrom(plaza.id),
              ),
            ),
          ),

        const SizedBox(height: ClaySpace.sm),
        ClayButton(
          label: l10n.plazasOpenFareTable,
          icon: Icons.grid_on_rounded,
          expand: true,
          onPressed: () => context.push(Routes.fares),
        ),
      ],
    );
  }

  /// The fare from the chosen origin to [plaza], or null when there is nothing honest to
  /// show — no origin picked, the plaza IS the origin, or the matrix has no row for this
  /// direction and vehicle class.
  Decimal? _fareTo(Plaza plaza) {
    final origin = state.fromPlaza;
    if (origin == null || plaza.id == origin.id) return null;
    return state.matrix
        .lookup(
          fromPlazaId: origin.id,
          toPlazaId: plaza.id,
          vehicleType: state.vehicleType,
        )
        ?.fare;
  }
}

/// One plaza row. Claymorphic — the spec's assignment for stacked list items.
class _PlazaRow extends StatelessWidget {
  const _PlazaRow({
    required this.plaza,
    required this.isOrigin,
    required this.fare,
    required this.onTap,
  });

  final Plaza plaza;
  final bool isOrigin;
  final Decimal? fare;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;
    final lanes = plaza.laneNumbers.length;

    return ClayCard(
      onTap: onTap,
      style: ClayDepthStyle.clay,
      semanticLabel: '${plaza.displayId} ${plaza.name}',
      child: Row(
        children: [
          // The plaza number on a recessed plate — the one deliberately skeuomorphic touch
          // in the app, borrowed from the enamel number signs on the gantries themselves.
          ClaySurface(
            style: ClayDepthStyle.pressed,
            radius: ClayRadius.control,
            width: 54,
            height: 42,
            borderColor: isOrigin ? palette.primary : null,
            child: Center(
              child: Text(
                plaza.displayId,
                style: textTheme.labelMedium?.copyWith(
                  color: isOrigin ? palette.primary : palette.textMuted,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.5,
                ),
                textDirection: TextDirection.ltr,
              ),
            ),
          ),
          const SizedBox(width: ClaySpace.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  plaza.name,
                  style: textTheme.titleMedium,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  isOrigin
                      ? l10n.plazasIsOrigin
                      : lanes == 0
                      ? l10n.plazasNoLanes
                      : l10n.plazasLaneCount(lanes),
                  style: textTheme.labelSmall,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          const SizedBox(width: ClaySpace.sm),
          if (fare != null)
            Text(
              Money.format(fare, locale: localeTag(context)),
              style: textTheme.titleMedium?.copyWith(color: palette.primary),
              textDirection: TextDirection.ltr,
            )
          else if (!isOrigin)
            Icon(
              Icons.chevron_right_rounded,
              color: palette.textMuted,
              size: 20,
            ),
        ],
      ),
    );
  }
}

class _PlazasSkeleton extends StatelessWidget {
  const _PlazasSkeleton();

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.all(ClaySpace.gutter),
    children: const [
      ClaySkeleton.line(height: 28, width: 160),
      SizedBox(height: ClaySpace.xl),
      ClaySkeletonCard(lines: 2, height: 96),
      SizedBox(height: ClaySpace.lg),
      ClaySkeletonCard(lines: 2, height: 76),
      SizedBox(height: ClaySpace.md),
      ClaySkeletonCard(lines: 2, height: 76),
      SizedBox(height: ClaySpace.md),
      ClaySkeletonCard(lines: 2, height: 76),
    ],
  );
}
