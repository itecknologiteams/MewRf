import 'dart:async';

import 'package:decimal/decimal.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/env/app_env.dart';
import 'package:mtag_user_app/core/errors/app_failure.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/topup.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/core/utils/money.dart';
import 'package:mtag_user_app/features/dashboard/presentation/wallet_controller.dart';
import 'package:mtag_user_app/features/topup/domain/payment_gateway.dart';

class TopupState {
  const TopupState({
    required this.accountId,
    this.amount,
    this.gatewayId,
    this.progress = const TopupIdle(),
    this.pending = const [],
    this.amountError,
    this.gatewayFields = const {},
  });

  final int? accountId;
  final Decimal? amount;
  final String? gatewayId;
  final TopupProgress progress;

  /// Top-ups that exist server-side and have not settled.
  ///
  /// Surfaced prominently because BOTH working paths can leave one: the aggregator
  /// flow is confirmed by a callback the app never sees, and the app-initiated flow has
  /// no checkout URL. A pending row the user cannot see is a user who pays twice.
  final List<TopupRequest> pending;

  final String? amountError;

  /// The `pp_*` fields from `/payments/topup/`, minus `pp_Password`.
  final Map<String, String> gatewayFields;

  bool get isBusy => progress is TopupSubmitting;

  bool get isWaiting => progress is TopupWaitingForConfirmation;
}

/// Not a family provider.
///
/// Riverpod 3's class-family API passes the argument through the create function
/// rather than into `build()`, which reads badly for something that also has to
/// change its target at runtime (a multi-vehicle holder switching wallets on this
/// screen). One instance that resolves a default and exposes [selectAccount] is
/// simpler and behaves identically — the deep link `mtag://topup?account=` calls
/// [selectAccount] on open.
class TopupController extends AsyncNotifier<TopupState> {
  StreamSubscription<TopupProgress>? _watch;

  /// Set before the first build by the screen, for `?account=`.
  int? _requestedAccountId;

  /// Idempotency keys already POSTed, per amount.
  ///
  /// `/payments/topup/` creates a `TopupRequest` row on every call and the server does
  /// not deduplicate, so a Retry tap on the same intent would leave two pending rows —
  /// which then both look like money owed, and the user cannot tell which one their
  /// payment belongs to. The key is generated once per INTENT and reused, so a retry
  /// re-sends the same key rather than minting a new one.
  final Map<String, String> _issuedKeys = {};

  /// topup ids this controller has already created, so a re-POST is impossible even if
  /// the key map is somehow bypassed.
  final Set<String> _spentIntents = {};

  @override
  Future<TopupState> build() async {
    ref.onDispose(() => _watch?.cancel());

    final resolved = _requestedAccountId ?? await _defaultAccountId();
    final pending = await _loadPending(resolved);

    return TopupState(
      accountId: resolved,
      pending: pending,
      // The aggregator flow is the default because it is the one that works end to
      // end. Putting an unconfigured path first would be worse than useless.
      gatewayId: const JazzCashAggregatorGateway().id,
    );
  }

  Future<int?> _defaultAccountId() async {
    final wallet = await ref.read(walletControllerProvider.future);
    return wallet.firstTopUpTarget?.accountId;
  }

  Future<List<TopupRequest>> _loadPending(int? accountId) async {
    if (accountId == null) return const [];
    try {
      final history = await ref
          .read(paymentRepositoryProvider)
          .topupHistory(accountId);
      return history
          .where((t) => t.status == TopupStatus.pending)
          .toList(growable: false);
    } on AppFailure {
      // A missing pending list must not block the screen — the user came here to pay.
      return const [];
    }
  }

  /// Points the screen at a different wallet.
  ///
  /// Safe to call before the first build resolves — the id is remembered and used as
  /// the default, which is what makes `?account=` work on a cold open.
  void selectAccount(int accountId) {
    _requestedAccountId = accountId;
    final current = state.value;
    if (current == null) return;
    state = AsyncValue.data(
      TopupState(
        accountId: accountId,
        gatewayId: current.gatewayId,
      ),
    );
    _refreshPending();
  }

  void selectGateway(String gatewayId) {
    final current = state.value;
    if (current == null) return;
    state = AsyncValue.data(
      TopupState(
        accountId: current.accountId,
        amount: current.amount,
        gatewayId: gatewayId,
        pending: current.pending,
      ),
    );
  }

  /// Sets the amount and validates it against the Rs. 100 floor.
  ///
  /// Validated as the user types so they are not bounced off a server rejection —
  /// but the server enforces the same rule in two places (`InitiateTopupSerializer`
  /// and `JazzCashService.initiate_topup`), and its wording is what gets shown if it
  /// ever disagrees with this.
  void setAmount(Decimal? amount) {
    final current = state.value;
    if (current == null) return;

    String? error;
    if (amount != null && amount < Money.fromInt(AppEnv.minimumTopupAmount)) {
      error = 'min';
    }

    state = AsyncValue.data(
      TopupState(
        accountId: current.accountId,
        amount: amount,
        gatewayId: current.gatewayId,
        pending: current.pending,
        amountError: error,
        progress: current.progress,
      ),
    );
  }

  /// Creates the pending top-up and starts polling for its resolution.
  ///
  /// Note what this method does NOT do: it never adds the amount to a displayed
  /// balance. There is no optimistic credit anywhere in this flow. The balance is
  /// re-read from the server once the top-up is confirmed, and until then the user sees
  /// their real balance plus a pending row.
  Future<void> submit() async {
    final current = state.value;
    final accountId = current?.accountId;
    final amount = current?.amount;
    if (current == null || accountId == null || amount == null) return;
    if (current.amountError != null || current.isBusy) return;

    final intent = '$accountId:${Money.toApiString(amount)}';
    if (_spentIntents.contains(intent)) {
      // Already created a pending row for this exact intent. Re-poll rather than
      // creating a second one.
      await _refreshPending();
      return;
    }

    final idempotencyKey = _issuedKeys.putIfAbsent(
      intent,
      // Derived from the intent plus a single timestamp captured the first time this
      // intent is submitted, so a retry of the SAME intent reuses the key while a
      // genuinely new top-up gets a fresh one.
      () => '$intent:${DateTime.now().microsecondsSinceEpoch}',
    );

    state = AsyncValue.data(
      TopupState(
        accountId: accountId,
        amount: amount,
        gatewayId: current.gatewayId,
        pending: current.pending,
        progress: const TopupSubmitting(),
      ),
    );

    try {
      final result = await ref
          .read(paymentRepositoryProvider)
          .initiateTopup(
            accountId: accountId,
            amount: amount,
            idempotencyKey: idempotencyKey,
          );
      _spentIntents.add(intent);

      state = AsyncValue.data(
        TopupState(
          accountId: accountId,
          amount: amount,
          gatewayId: current.gatewayId,
          pending: current.pending,
          gatewayFields: result.gatewayFields,
          progress: TopupWaitingForConfirmation(
            topupId: result.topupId,
            amount: amount,
            attempt: 0,
          ),
        ),
      );

      _startWatching(
        accountId: accountId,
        topupId: result.topupId,
        amount: amount,
      );
    } on AppFailure catch (failure) {
      state = AsyncValue.data(
        TopupState(
          accountId: accountId,
          amount: amount,
          gatewayId: current.gatewayId,
          pending: current.pending,
          progress: TopupFailed(reason: failure.message ?? ''),
          // The server's own wording wins over the client's copy of the rule.
          amountError: failure.fieldErrors?['amount'],
        ),
      );
    }
  }

  /// Polls the server until the top-up settles.
  ///
  /// The ONLY thing treated as evidence of payment. Not a WebView redirect, not a
  /// gateway success page, not the user saying they paid — the top-up leaving `pending`
  /// in the server's own record.
  void _startWatching({
    required int accountId,
    required int topupId,
    required Decimal amount,
  }) {
    _watch?.cancel();
    _watch = ref
        .read(paymentRepositoryProvider)
        .watchTopup(accountId: accountId, topupId: topupId, amount: amount)
        .listen((progress) async {
          final current = state.value;
          if (current == null) return;

          if (progress is TopupConfirmed) {
            // Re-read the balance from the SERVER. Never old + amount: the gateway may have
            // settled a different figure, and a toll could have been deducted while the
            // payment was in flight.
            await ref.read(walletControllerProvider.notifier).refreshBalances();
            final refreshed = await _serverBalance(accountId);
            state = AsyncValue.data(
              TopupState(
                accountId: accountId,
                gatewayId: current.gatewayId,
                pending: await _loadPending(accountId),
                progress: TopupConfirmed(
                  amount: progress.amount,
                  newBalance: refreshed,
                ),
              ),
            );
            return;
          }

          state = AsyncValue.data(
            TopupState(
              accountId: current.accountId,
              amount: current.amount,
              gatewayId: current.gatewayId,
              pending: current.pending,
              gatewayFields: current.gatewayFields,
              progress: progress,
            ),
          );
        });
  }

  Future<Decimal?> _serverBalance(int accountId) async {
    final wallet = ref.read(walletControllerProvider).value;
    return wallet?.vehicles
        .where((v) => v.accountId == accountId)
        .firstOrNull
        ?.balance;
  }

  /// Called when the in-app WebView hits the return URL.
  ///
  /// It starts a poll and nothing else. The redirect means "the browser came back",
  /// which is not the same as "the account was credited" — the gateway callback is
  /// asynchronous and may not have fired, or may have failed.
  Future<void> onCheckoutReturned() async {
    final current = state.value;
    final progress = current?.progress;
    if (current == null || progress is! TopupWaitingForConfirmation) return;
    _startWatching(
      accountId: current.accountId!,
      topupId: progress.topupId,
      amount: progress.amount,
    );
  }

  /// Re-checks the pending list. The aggregator flow's only feedback channel: the user
  /// pays in the JazzCash app and comes back here.
  Future<void> refreshPending() => _refreshPending();

  Future<void> _refreshPending() async {
    final current = state.value;
    if (current == null) return;
    final pending = await _loadPending(current.accountId);
    await ref.read(walletControllerProvider.notifier).refreshBalances();
    state = AsyncValue.data(
      TopupState(
        accountId: current.accountId,
        amount: current.amount,
        gatewayId: current.gatewayId,
        pending: pending,
        gatewayFields: current.gatewayFields,
        progress: current.progress,
      ),
    );
  }

  void reset() {
    _watch?.cancel();
    final current = state.value;
    if (current == null) return;
    state = AsyncValue.data(
      TopupState(
        accountId: current.accountId,
        gatewayId: current.gatewayId,
        pending: current.pending,
      ),
    );
  }
}

/// autoDispose so the pending-poll subscription and the idempotency-key map are
/// dropped when the user leaves the screen — a stale poll writing into a disposed
/// state, or a reused key from a previous visit, would both be wrong.
final AsyncNotifierProvider<TopupController, TopupState>
topupControllerProvider =
    AsyncNotifierProvider.autoDispose<TopupController, TopupState>(
      TopupController.new,
    );
