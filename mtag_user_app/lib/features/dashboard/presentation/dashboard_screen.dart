import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mtag_user_app/core/router/app_router.dart';
import 'package:mtag_user_app/core/utils/app_dates.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/auth/presentation/session_controller.dart';
import 'package:mtag_user_app/features/dashboard/presentation/wallet_controller.dart';
import 'package:mtag_user_app/features/dashboard/presentation/widgets/balance_hero_card.dart';
import 'package:mtag_user_app/features/dashboard/presentation/widgets/low_balance_banner.dart';
import 'package:mtag_user_app/features/dashboard/presentation/widgets/stat_tiles.dart';
import 'package:mtag_user_app/features/dashboard/presentation/widgets/tag_rail.dart';
import 'package:mtag_user_app/features/shared/staff_account_notice.dart';
import 'package:mtag_user_app/features/transactions/presentation/widgets/transaction_row.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final session = ref.watch(sessionControllerProvider).value;

    // An operator or admin can authenticate with these credentials. Rather than show
    // them a dashboard whose every call is scoped to consumer ownership — and which
    // would mostly render empty — the app says what happened and offers a way out.
    if (session is SessionSignedIn && session.isStaffAccount) {
      return const StaffAccountNotice();
    }

    final async = ref.watch(walletControllerProvider);
    final user = ref.watch(currentUserProvider);

    return Scaffold(
      backgroundColor: palette.base,
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          onRefresh: () =>
              ref.read(walletControllerProvider.notifier).refresh(),
          color: palette.primary,
          backgroundColor: palette.surface,
          child: async.when(
            loading: _DashboardSkeleton.new,
            error: (error, _) => ListView(
              padding: const EdgeInsets.all(ClaySpace.gutter),
              children: [
                SizedBox(height: MediaQuery.sizeOf(context).height * 0.15),
                ClayErrorState(
                  message: describeError(error, l10n),
                  retryLabel: l10n.actionRetry,
                  onRetry: () =>
                      ref.read(walletControllerProvider.notifier).refresh(),
                ),
              ],
            ),
            data: (snapshot) => _DashboardBody(
              snapshot: snapshot,
              greeting: user == null
                  ? l10n.appName
                  : l10n.dashboardGreeting(_firstName(user.fullName)),
            ),
          ),
        ),
      ),
    );
  }

  /// First name only. A greeting is a greeting, and "Hello, Muhammad Asif Raza Khan"
  /// wraps onto two lines on a narrow phone and pushes the balance card down.
  static String _firstName(String fullName) {
    final trimmed = fullName.trim();
    if (trimmed.isEmpty) return '';
    return trimmed.split(RegExp(r'\s+')).first;
  }
}

class _DashboardBody extends ConsumerWidget {
  const _DashboardBody({required this.snapshot, required this.greeting});

  final WalletSnapshot snapshot;
  final String greeting;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppL10n.of(context);
    final textTheme = Theme.of(context).textTheme;
    final recent = snapshot.summary?.recentTransactions ?? const [];

    return ListView(
      // Always scrollable so pull-to-refresh works even when the content is short —
      // an empty dashboard is exactly when a user wants to pull.
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.only(
        left: ClaySpace.gutter,
        right: ClaySpace.gutter,
        top: ClaySpace.lg,
        bottom: ClaySpace.xl,
      ),
      children: [
        // Each section fades and lifts in, staggered. The order is the reading order, so
        // the eye is led down the page once rather than everything appearing at once.
        ClayEntrance(child: Text(greeting, style: textTheme.headlineMedium)),
        const SizedBox(height: ClaySpace.xl),

        if (snapshot.isStale) ...[
          ClayStaleRibbon(
            message: l10n.offlineShowingSaved(
              AppDates.relative(snapshot.storedAt, locale: localeTag(context)),
            ),
            onRefresh: () =>
                ref.read(walletControllerProvider.notifier).refresh(),
          ),
          const SizedBox(height: ClaySpace.cardGap),
        ],

        ClayEntrance(
          index: 1,
          child: BalanceHeroCard(
            total: snapshot.total,
            tagCount: snapshot.vehiclesWithTags.length,
            onTopUp: () => context.push(
              Routes.topupPath(accountId: snapshot.firstTopUpTarget?.accountId),
            ),
          ),
        ),
        const SizedBox(height: ClaySpace.cardGap),

        // The urgent banner comes BEFORE the stats: a driver whose tag will be refused
        // at the barrier needs that before they need this month's toll total.
        ClayEntrance(
          index: 2,
          child: LowBalanceBanner(
            blocked: snapshot.blockedVehicles,
            low: snapshot.lowVehicles,
            onTopUp: (vehicle) =>
                context.push(Routes.topupPath(accountId: vehicle.accountId)),
          ),
        ),

        ClayEntrance(index: 3, child: StatTiles(snapshot: snapshot)),
        const SizedBox(height: ClaySpace.xl),

        if (snapshot.vehicles.isEmpty)
          ClayEmptyState(
            icon: Icons.sensors_off_rounded,
            title: l10n.dashboardNoTagsTitle,
            message: l10n.dashboardNoTagsBody,
          )
        else ...[
          _SectionHeader(
            title: l10n.dashboardYourTags,
            actionLabel: l10n.actionViewAll,
            onAction: () => context.go(Routes.tags),
          ),
          const SizedBox(height: ClaySpace.md),
          ClayEntrance(index: 4, child: TagRail(vehicles: snapshot.vehicles)),
          const SizedBox(height: ClaySpace.xl),
        ],

        if (recent.isNotEmpty) ...[
          _SectionHeader(
            title: l10n.dashboardRecentActivity,
            actionLabel: l10n.actionViewAll,
            onAction: () => context.go(Routes.activity),
          ),
          const SizedBox(height: ClaySpace.md),
          ClayCard(
            padding: const EdgeInsets.symmetric(vertical: ClaySpace.sm),
            child: Column(
              children: [
                // Merged across every account, newest first — so a two-vehicle holder
                // sees one feed rather than having to check each tag.
                for (final transaction in recent.take(5))
                  TransactionRow(
                    transaction: transaction,
                    showPlate: snapshot.vehicles.length > 1,
                  ),
              ],
            ),
          ),
          const SizedBox(height: ClaySpace.md),
          Text(
            // Booths run offline and sync every 30s, so this list is never live. Saying
            // so up front stops a driver concluding their exit was not recorded.
            l10n.transactionsNotRealtime,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({
    required this.title,
    this.actionLabel,
    this.onAction,
  });

  final String title;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(title, style: Theme.of(context).textTheme.titleLarge),
        ),
        if (actionLabel != null && onAction != null)
          ClayButton(
            label: actionLabel!,
            variant: ClayButtonVariant.ghost,
            padding: const EdgeInsets.symmetric(
              horizontal: ClaySpace.md,
              vertical: ClaySpace.sm,
            ),
            onPressed: onAction,
          ),
      ],
    );
  }
}

/// Skeletons in the shape of the real dashboard, so nothing jumps when data lands.
class _DashboardSkeleton extends StatelessWidget {
  const _DashboardSkeleton();

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.only(
        left: ClaySpace.gutter,
        right: ClaySpace.gutter,
        top: ClaySpace.lg,
        bottom: ClaySpace.xl,
      ),
      children: const [
        ClaySkeleton.line(width: 180, height: 26),
        SizedBox(height: ClaySpace.xl),
        ClaySkeletonCard(height: 210, depth: ClayDepth.hero),
        SizedBox(height: ClaySpace.cardGap),
        Row(
          children: [
            Expanded(child: ClaySkeletonCard(lines: 2, height: 104)),
            SizedBox(width: ClaySpace.md),
            Expanded(child: ClaySkeletonCard(lines: 2, height: 104)),
            SizedBox(width: ClaySpace.md),
            Expanded(child: ClaySkeletonCard(lines: 2, height: 104)),
          ],
        ),
        SizedBox(height: ClaySpace.xl),
        ClaySkeleton.line(width: 120, height: 20),
        SizedBox(height: ClaySpace.md),
        ClaySkeletonCard(height: 150),
      ],
    );
  }
}
