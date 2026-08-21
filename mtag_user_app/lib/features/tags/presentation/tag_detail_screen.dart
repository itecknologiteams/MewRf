import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mtag_user_app/core/models/tag.dart';
import 'package:mtag_user_app/core/models/vehicle.dart';
import 'package:mtag_user_app/core/router/app_router.dart';
import 'package:mtag_user_app/core/security/screen_security.dart';
import 'package:mtag_user_app/core/utils/app_dates.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/dashboard/presentation/wallet_controller.dart';
import 'package:mtag_user_app/features/shared/detail_row.dart';
import 'package:mtag_user_app/features/shared/money_text.dart';
import 'package:mtag_user_app/features/shared/tag_status_badge.dart';
import 'package:mtag_user_app/features/tags/presentation/widgets/tag_pass_card.dart';
import 'package:mtag_user_app/features/transactions/presentation/transactions_controller.dart';
import 'package:mtag_user_app/features/transactions/presentation/widgets/transaction_row.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// One tag, in full.
///
/// Reached by serial rather than id, so the deep link `mtag://tag/{serial}` works from
/// a printed receipt or an SMS — a tag's serial is on the physical tag, its database id
/// is not.
class TagDetailScreen extends ConsumerStatefulWidget {
  const TagDetailScreen({required this.tagSerial, super.key});

  final String tagSerial;

  @override
  ConsumerState<TagDetailScreen> createState() => _TagDetailScreenState();
}

class _TagDetailScreenState extends ConsumerState<TagDetailScreen> {
  @override
  void initState() {
    super.initState();
    // The TID is on this screen. Anyone holding it can pay into — and inspect the
    // balance of — this wallet through the JazzCash aggregator flow, so the screen is
    // not screenshottable and does not appear in the recents thumbnail.
    ScreenSecurity.instance.enable();
  }

  @override
  void dispose() {
    ScreenSecurity.instance.disable();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final vehicle = ref.watch(vehicleByTagSerialProvider(widget.tagSerial));

    if (vehicle == null) {
      // The wallet has not loaded yet, or this serial is not the user's. Both resolve
      // by going back to a list that is definitely correct.
      return ClayScaffold(
        title: l10n.tagsTitle,
        showBack: true,
        body: ClayEmptyState(
          icon: Icons.search_off_rounded,
          title: l10n.errorNotFound,
          message: l10n.tagsEmptyBody,
          actionLabel: l10n.actionBack,
          onAction: () => context.pop(),
        ),
      );
    }

    return _TagDetailBody(vehicle: vehicle);
  }
}

class _TagDetailBody extends ConsumerWidget {
  const _TagDetailBody({required this.vehicle});

  final MyVehicle vehicle;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppL10n.of(context);
    final textTheme = Theme.of(context).textTheme;
    final tag = vehicle.tag!;
    final accountId = vehicle.accountId;

    return ClayScaffold(
      title: vehicle.plateNumber,
      subtitle: tag.tagSerial,
      showBack: true,
      body: ListView(
        padding: const EdgeInsets.only(bottom: ClaySpace.xxl),
        children: [
          // The TID block.
          //
          // Hidden entirely when the server does not report a TID, rather than shown
          // as an empty field beside an instruction to type it into JazzCash. An older
          // backend omits `tid` from TagSerializer, and a blank box under "enter this
          // in JazzCash" is worse than no box.
          if (tag.canShowJazzCashInstructions)
            TagPassCard(tag: tag, plateNumber: vehicle.plateNumber)
          else
            ClayBanner(
              icon: Icons.info_outline_rounded,
              title: l10n.topupJazzCashNoTidTitle,
              message: l10n.topupJazzCashNoTidBody,
            ),
          const SizedBox(height: ClaySpace.cardGap),

          // Balance and the top-up CTA, directly under the pass.
          ClayCard(
            depth: ClayDepth.hero,
            radius: ClayRadius.hero,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            l10n.vehicleBalance,
                            style: textTheme.labelMedium,
                          ),
                          const SizedBox(height: ClaySpace.xs),
                          BalanceFigure(
                            amount: vehicle.balance,
                            level: vehicle.balanceLevel,
                            style: textTheme.displayLarge,
                            showWarningIcon: false,
                          ),
                        ],
                      ),
                    ),
                    // The gauge against the Rs. 50 entry minimum: the one number that
                    // decides whether the barrier opens.
                    EntryReadinessRing(balance: vehicle.balance),
                  ],
                ),
                if (vehicle.balanceUpdatedAt != null) ...[
                  const SizedBox(height: ClaySpace.sm),
                  Text(
                    l10n.offlineBalanceAge(
                      AppDates.relative(
                        vehicle.balanceUpdatedAt,
                        locale: localeTag(context),
                      ),
                    ),
                    style: textTheme.labelSmall,
                  ),
                ],
                const SizedBox(height: ClaySpace.xl),
                ClayButton(
                  label: l10n.actionTopUp,
                  icon: Icons.add_rounded,
                  variant: ClayButtonVariant.primary,
                  expand: true,
                  onPressed: accountId == null
                      ? null
                      : () => context.push(
                          Routes.topupPath(accountId: accountId),
                        ),
                ),
              ],
            ),
          ),
          const SizedBox(height: ClaySpace.cardGap),

          ClayCard(
            onTap: () => context.push(Routes.vehicleDetailPath(vehicle.id)),
            semanticLabel: l10n.tagLinkedVehicle,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l10n.tagLinkedVehicle, style: textTheme.titleLarge),
                const SizedBox(height: ClaySpace.lg),
                Row(
                  children: [
                    Expanded(child: PlateNumber(vehicle.plateNumber)),
                    FareClassPill(vehicleType: vehicle.vehicleType),
                  ],
                ),
                const SizedBox(height: ClaySpace.md),
                DetailRow(
                  label: l10n.vehicleRegistered,
                  value: AppDates.date(
                    vehicle.registeredAt,
                    locale: localeTag(context),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: ClaySpace.cardGap),

          if (accountId != null) _RecentTransactions(accountId: accountId),
        ],
      ),
    );
  }
}

class _RecentTransactions extends ConsumerWidget {
  const _RecentTransactions({required this.accountId});

  final int accountId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppL10n.of(context);
    final async = ref.watch(accountTransactionsProvider(accountId));

    return ClayCard(
      padding: const EdgeInsets.symmetric(vertical: ClaySpace.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: ClaySpace.lg),
            child: Text(
              l10n.dashboardRecentActivity,
              style: Theme.of(context).textTheme.titleLarge,
            ),
          ),
          const SizedBox(height: ClaySpace.md),
          async.when(
            loading: () => const Padding(
              padding: EdgeInsets.symmetric(horizontal: ClaySpace.lg),
              child: Column(
                children: [
                  ClaySkeleton.line(),
                  SizedBox(height: ClaySpace.md),
                  ClaySkeleton.line(width: 180),
                ],
              ),
            ),
            error: (error, _) => Padding(
              padding: const EdgeInsets.symmetric(horizontal: ClaySpace.lg),
              child: Text(
                describeError(error, l10n),
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
            data: (transactions) => transactions.isEmpty
                ? Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: ClaySpace.lg,
                    ),
                    child: Text(
                      l10n.transactionsEmptyBody,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  )
                : Column(
                    children: [
                      for (final transaction in transactions.take(6))
                        TransactionRow(transaction: transaction),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}
