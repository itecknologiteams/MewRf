import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/toll.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/fares/presentation/fares_controller.dart';
import 'package:mtag_user_app/features/shared/money_text.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Fare lookup between two plazas, for one fare class.
///
/// Built around the fact that **fares are directional**: A→B and B→A are separate rows in
/// `fare_matrix` and can differ. So the UI never says "the fare between X and Y" — it
/// shows a from, a to, an explicit swap control, and a note saying the reverse may
/// differ.
class FaresScreen extends ConsumerWidget {
  const FaresScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppL10n.of(context);
    final async = ref.watch(faresControllerProvider);

    return ClayScaffold(
      title: l10n.faresTitle,
      subtitle: l10n.faresSubtitle,
      showBack: true,
      body: async.when(
        loading: () => ListView(
          physics: const NeverScrollableScrollPhysics(),
          children: const [
            ClaySkeletonCard(height: 180),
            SizedBox(height: ClaySpace.cardGap),
            ClaySkeletonCard(lines: 2, height: 120),
          ],
        ),
        error: (error, _) => ClayErrorState(
          message: describeError(error, l10n),
          retryLabel: l10n.actionRetry,
          onRetry: () => ref.read(faresControllerProvider.notifier).refresh(),
        ),
        data: (state) {
          if (state.plazas.isEmpty || state.matrix.isEmpty) {
            return ClayEmptyState(
              icon: Icons.price_change_outlined,
              title: l10n.faresEmptyTitle,
              message: l10n.faresEmptyBody,
              actionLabel: l10n.actionRetry,
              onAction: () =>
                  ref.read(faresControllerProvider.notifier).refresh(),
            );
          }
          return _FaresBody(state: state);
        },
      ),
    );
  }
}

class _FaresBody extends ConsumerWidget {
  const _FaresBody({required this.state});

  final FaresState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppL10n.of(context);
    final controller = ref.read(faresControllerProvider.notifier);
    final textTheme = Theme.of(context).textTheme;

    return ListView(
      padding: const EdgeInsets.only(bottom: ClaySpace.xxl),
      children: [
        ClayCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _PlazaPicker(
                label: l10n.faresFrom,
                icon: Icons.trip_origin_rounded,
                plazas: state.plazas,
                selectedId: state.fromPlazaId,
                onSelected: controller.setFrom,
              ),
              const SizedBox(height: ClaySpace.md),
              // The swap button is load-bearing, not a convenience: it looks up a
              // different row, and the fare can change.
              Align(
                alignment: AlignmentDirectional.centerEnd,
                child: ClayIconButton(
                  icon: Icons.swap_vert_rounded,
                  semanticLabel: l10n.faresSwap,
                  onPressed: controller.swap,
                ),
              ),
              const SizedBox(height: ClaySpace.md),
              _PlazaPicker(
                label: l10n.faresTo,
                icon: Icons.place_rounded,
                plazas: state.plazas,
                selectedId: state.toPlazaId,
                onSelected: controller.setTo,
              ),
            ],
          ),
        ),
        const SizedBox(height: ClaySpace.cardGap),

        ClayCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(l10n.faresVehicleClass, style: textTheme.titleMedium),
              const SizedBox(height: ClaySpace.md),
              Wrap(
                spacing: ClaySpace.sm,
                runSpacing: ClaySpace.sm,
                children: [
                  // Only classes the operator has actually published rates for. Offering
                  // a class with no rows would produce a "no fare set" for something the
                  // app itself suggested.
                  for (final type in _orderedTypes(state.matrix.availableTypes))
                    ClayFilterChip(
                      label: type.label(l10n),
                      selected: state.vehicleType == type,
                      onTap: () => controller.setVehicleType(type),
                    ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: ClaySpace.cardGap),

        _FareResult(state: state),
      ],
    );
  }

  /// Notification order, not alphabetical — it is how the printed fare schedule reads.
  static List<VehicleType> _orderedTypes(Set<VehicleType> available) => [
    for (final type in VehicleType.values)
      if (available.contains(type) && type != VehicleType.unknown) type,
  ];
}

class _FareResult extends StatelessWidget {
  const _FareResult({required this.state});

  final FaresState state;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final textTheme = Theme.of(context).textTheme;

    if (!state.hasSelection) {
      return ClayBanner(
        icon: Icons.touch_app_outlined,
        title: l10n.faresPickPlazas,
        tone: ClayTone.neutral,
      );
    }

    // A motorcycle is a valid registration class but is not permitted on the expressway,
    // so there is no fare to quote — and quoting one would imply it may travel.
    if (state.vehicleType == VehicleType.motorcycle) {
      return ClayBanner(
        icon: Icons.do_not_disturb_on_outlined,
        title: l10n.faresMotorcycleTitle,
        message: l10n.faresMotorcycleBody,
      );
    }

    final fare = state.fare;
    if (fare == null) {
      return ClayBanner(
        icon: Icons.help_outline_rounded,
        title: l10n.faresNotSetTitle,
        message: l10n.faresNotSetBody,
      );
    }

    return ClayCard(
      depth: ClayDepth.hero,
      radius: ClayRadius.hero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l10n.faresResult, style: textTheme.labelMedium),
          const SizedBox(height: ClaySpace.xs),
          MoneyText(fare.fare, style: textTheme.displayLarge),
          const SizedBox(height: ClaySpace.lg),
          Row(
            children: [
              Expanded(
                child: Text(
                  '${fare.fromPlazaName} → ${fare.toPlazaName}',
                  style: textTheme.bodyMedium,
                ),
              ),
            ],
          ),
          const SizedBox(height: ClaySpace.sm),
          Text(
            l10n.faresDirectionNote(fare.fromPlazaName, fare.toPlazaName),
            style: textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

/// A plaza picker in a clay sheet.
///
/// A sheet rather than a `DropdownButton`: Material's dropdown paints a flat elevated
/// menu with its own divider, which is the one shape this design system does not
/// contain. It also shows the operator's `display_id` beside each name, since 105 and 106
/// are both "Quaidabad Interchange" and the number is the only thing telling them apart.
class _PlazaPicker extends StatelessWidget {
  const _PlazaPicker({
    required this.label,
    required this.icon,
    required this.plazas,
    required this.selectedId,
    required this.onSelected,
  });

  final String label;
  final IconData icon;
  final List<Plaza> plazas;
  final int? selectedId;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;
    final selected = plazas.where((p) => p.id == selectedId).firstOrNull;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: textTheme.labelMedium),
        const SizedBox(height: ClaySpace.sm),
        GestureDetector(
          onTap: () => _open(context),
          child: ClaySurface(
            style: ClayDepthStyle.pressed,
            depth: ClayDepth.control,
            radius: ClayRadius.control,
            padding: const EdgeInsets.symmetric(
              horizontal: ClaySpace.lg,
              vertical: ClaySpace.lg,
            ),
            child: Row(
              children: [
                Icon(icon, size: 18, color: palette.textMuted),
                const SizedBox(width: ClaySpace.md),
                Expanded(
                  child: Text(
                    selected?.name ?? AppL10n.of(context).faresPickPlazas,
                    style: textTheme.bodyLarge?.copyWith(
                      color: selected == null
                          ? palette.textMuted
                          : palette.textPrimary,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Icon(
                  Icons.expand_more_rounded,
                  size: 20,
                  color: palette.textMuted,
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  void _open(BuildContext context) {
    showClaySheet<void>(
      context: context,
      builder: (sheetContext) => SizedBox(
        height: MediaQuery.sizeOf(sheetContext).height * 0.55,
        child: ListView.separated(
          itemCount: plazas.length,
          separatorBuilder: (_, _) => const SizedBox(height: ClaySpace.sm),
          itemBuilder: (context, index) {
            final plaza = plazas[index];
            return ClayCard(
              depth: plaza.id == selectedId
                  ? ClayDepth.nested
                  : ClayDepth.control,
              padding: const EdgeInsets.all(ClaySpace.lg),
              onTap: () {
                onSelected(plaza.id);
                Navigator.of(sheetContext).pop();
              },
              child: Row(
                children: [
                  Text(
                    plaza.displayId,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      fontFamily: 'Mono',
                    ),
                    textDirection: TextDirection.ltr,
                  ),
                  const SizedBox(width: ClaySpace.md),
                  Expanded(
                    child: Text(
                      plaza.name,
                      style: Theme.of(context).textTheme.bodyLarge,
                    ),
                  ),
                  if (plaza.id == selectedId)
                    Icon(
                      Icons.check_rounded,
                      size: 18,
                      color: ClayTheme.of(context).palette.primaryOnSurface,
                    ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}
