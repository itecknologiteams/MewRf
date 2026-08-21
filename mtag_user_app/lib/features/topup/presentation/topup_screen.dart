import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/models/topup.dart';
import 'package:mtag_user_app/core/models/vehicle.dart';
import 'package:mtag_user_app/core/security/screen_security.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/dashboard/presentation/wallet_controller.dart';
import 'package:mtag_user_app/features/shared/money_text.dart';
import 'package:mtag_user_app/features/shared/tag_status_badge.dart';
import 'package:mtag_user_app/features/topup/domain/payment_gateway.dart';
import 'package:mtag_user_app/features/topup/presentation/topup_controller.dart';
import 'package:mtag_user_app/features/topup/presentation/widgets/amount_step.dart';
import 'package:mtag_user_app/features/topup/presentation/widgets/gateway_list.dart';
import 'package:mtag_user_app/features/topup/presentation/widgets/gateway_panels.dart';
import 'package:mtag_user_app/features/topup/presentation/widgets/pending_topups.dart';
import 'package:mtag_user_app/features/topup/presentation/widgets/topup_progress_view.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// The top-up screen.
///
/// Structured around one uncomfortable truth the design has to carry rather than hide:
/// of the five payment methods, exactly one works end to end today — and it is the one
/// where **this app is not in the loop at all**. The customer pays from the JazzCash
/// app using their TID; JazzCash calls the server; the server credits the account.
///
/// So the screen leads with instructions rather than a checkout, treats the
/// app-initiated flow as unconfigured unless a checkout URL is supplied, renders
/// Easypaisa and card as coming-soon with a real alternative, and ends every path by
/// reconciling against a server read.
class TopupScreen extends ConsumerStatefulWidget {
  const TopupScreen({this.initialAccountId, super.key});

  final int? initialAccountId;

  @override
  ConsumerState<TopupScreen> createState() => _TopupScreenState();
}

class _TopupScreenState extends ConsumerState<TopupScreen> {
  @override
  void initState() {
    super.initState();
    // A TID and a balance are both on this screen, and the TID is enough for a stranger
    // to pay into (and read the balance of) this wallet.
    ScreenSecurity.instance.enable();

    // The `?account=` deep link. Applied after the first frame so the provider is
    // created before it is written to, and a no-op when the link carried no account —
    // the controller then picks the wallet that most needs topping up.
    final requested = widget.initialAccountId;
    if (requested != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        ref.read(topupControllerProvider.notifier).selectAccount(requested);
      });
    }
  }

  @override
  void dispose() {
    ScreenSecurity.instance.disable();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final provider = topupControllerProvider;
    final async = ref.watch(provider);
    final wallet = ref.watch(walletControllerProvider).value;

    return ClayScaffold(
      title: l10n.topupTitle,
      showBack: true,
      body: async.when(
        loading: () => ListView(
          physics: const NeverScrollableScrollPhysics(),
          children: const [
            ClaySkeletonCard(height: 160),
            SizedBox(height: ClaySpace.cardGap),
            ClaySkeletonCard(lines: 4),
          ],
        ),
        error: (error, _) => ClayErrorState(
          message: describeError(error, l10n),
          retryLabel: l10n.actionRetry,
          onRetry: () async => ref.invalidate(provider),
        ),
        data: (state) {
          final vehicle = wallet?.vehicles
              .where((v) => v.accountId == state.accountId)
              .firstOrNull;

          // Mid-flight, the progress view owns the whole screen. Leaving the amount
          // field and the Pay button on screen next to "waiting for confirmation" is
          // how a user ends up paying twice.
          if (state.progress is! TopupIdle) {
            return TopupProgressView(
              state: state,
              vehicle: vehicle,
              onDone: () => Navigator.of(context).maybePop(),
              onRetry: () => ref.read(provider.notifier).reset(),
              onCheckAgain: () => ref.read(provider.notifier).refreshPending(),
            );
          }

          if (state.accountId == null || vehicle == null) {
            return ClayEmptyState(
              icon: Icons.account_balance_wallet_outlined,
              title: l10n.tagsEmptyTitle,
              message: l10n.tagsEmptyBody,
            );
          }

          return _TopupForm(
            state: state,
            vehicle: vehicle,
            vehicles: wallet?.vehicles ?? const [],
            onSelectAccount: (accountId) =>
                ref.read(provider.notifier).selectAccount(accountId),
            onSelectGateway: (id) =>
                ref.read(provider.notifier).selectGateway(id),
            onAmountChanged: (amount) =>
                ref.read(provider.notifier).setAmount(amount),
            onSubmit: () => ref.read(provider.notifier).submit(),
            onRefreshPending: () =>
                ref.read(provider.notifier).refreshPending(),
          );
        },
      ),
    );
  }
}

class _TopupForm extends StatelessWidget {
  const _TopupForm({
    required this.state,
    required this.vehicle,
    required this.vehicles,
    required this.onSelectAccount,
    required this.onSelectGateway,
    required this.onAmountChanged,
    required this.onSubmit,
    required this.onRefreshPending,
  });

  final TopupState state;
  final MyVehicle vehicle;
  final List<MyVehicle> vehicles;
  final ValueChanged<int> onSelectAccount;
  final ValueChanged<String> onSelectGateway;
  final ValueChanged<Decimal?> onAmountChanged;
  final VoidCallback onSubmit;
  final Future<void> Function() onRefreshPending;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final textTheme = Theme.of(context).textTheme;

    final gateway = paymentGateways.firstWhere(
      (g) => g.id == state.gatewayId,
      orElse: () => const JazzCashAggregatorGateway(),
    );
    final context0 = GatewayContext(
      accountId: vehicle.accountId!,
      plateNumber: vehicle.plateNumber,
      tid: vehicle.tag?.tid,
    );

    return ListView(
      padding: const EdgeInsets.only(bottom: ClaySpace.xxl),
      children: [
        // Which wallet. Explicit even for a single-vehicle holder: money is going into
        // one specific tag's balance, and "top up" without a subject is how the wrong
        // vehicle gets credited.
        ClayCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                l10n.topupForVehicle(vehicle.plateNumber),
                style: textTheme.titleLarge,
              ),
              const SizedBox(height: ClaySpace.md),
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          l10n.topupCurrentBalance,
                          style: textTheme.labelSmall,
                        ),
                        const SizedBox(height: 2),
                        BalanceFigure(
                          amount: vehicle.balance,
                          level: vehicle.balanceLevel,
                          style: textTheme.displaySmall,
                        ),
                      ],
                    ),
                  ),
                  TagStatusBadge(tag: vehicle.tag, dense: true),
                ],
              ),
              if (vehicles.length > 1) ...[
                const SizedBox(height: ClaySpace.lg),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      for (final option in vehicles)
                        if (option.accountId != null) ...[
                          ClayFilterChip(
                            label: option.plateNumber,
                            selected: option.accountId == state.accountId,
                            onTap: () => onSelectAccount(option.accountId!),
                          ),
                          const SizedBox(width: ClaySpace.sm),
                        ],
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: ClaySpace.cardGap),

        // Pending top-ups, above everything. Both working paths can leave one, and a
        // user who cannot see theirs pays again.
        if (state.pending.isNotEmpty) ...[
          PendingTopups(pending: state.pending, onCheckAgain: onRefreshPending),
          const SizedBox(height: ClaySpace.cardGap),
        ],

        Text(l10n.topupChooseMethod, style: textTheme.titleLarge),
        const SizedBox(height: ClaySpace.md),
        GatewayList(
          selectedId: state.gatewayId,
          gatewayContext: context0,
          onSelect: onSelectGateway,
        ),
        const SizedBox(height: ClaySpace.cardGap),

        // The panel for the chosen method. Each one is honest about what it can do:
        // the aggregator shows the TID and instructions, the checkout shows either a
        // Pay button or a plain "not set up", cash shows where to go, and the two
        // unimplemented methods show an alternative rather than a dead button.
        GatewayPanel(
          gateway: gateway,
          gatewayContext: context0,
          child:
              gateway.acceptsAmountFromApp &&
                  gateway.availabilityFor(context0) ==
                      GatewayAvailability.available
              ? AmountStep(
                  amount: state.amount,
                  currentBalance: vehicle.balance,
                  errorKey: state.amountError,
                  onChanged: onAmountChanged,
                  onSubmit: onSubmit,
                  isBusy: state.isBusy,
                )
              : null,
        ),
      ],
    );
  }
}
