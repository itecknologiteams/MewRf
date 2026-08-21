import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/errors/app_failure.dart';
import 'package:mtag_user_app/core/models/account.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/vehicle.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/core/utils/app_dates.dart';
import 'package:mtag_user_app/features/dashboard/presentation/wallet_controller.dart';

/// The Activity filter chips. Maps onto `?type=`, filtered SERVER-side.
///
/// Server-side because filtering one fetched page locally would show "3 tolls" for an
/// account with two hundred — the page is 20 rows, not the whole history.
enum TransactionFilter {
  all(null),
  tolls(TransactionType.tollDeduction),
  topups(TransactionType.topup),
  refunds(TransactionType.refund);

  const TransactionFilter(this.type);

  final TransactionType? type;
}

/// A day's worth of transactions, for the sticky headers.
class TransactionDay {
  const TransactionDay({required this.day, required this.transactions});

  /// Midnight PKT, as a UTC instant.
  final DateTime day;
  final List<Transaction> transactions;
}

class TransactionsState {
  const TransactionsState({
    this.days = const [],
    this.filter = TransactionFilter.all,
    this.isLoadingMore = false,
    this.hasMore = false,
    this.totalCount = 0,
    this.selectedAccountId,
  });

  final List<TransactionDay> days;
  final TransactionFilter filter;
  final bool isLoadingMore;
  final bool hasMore;
  final int totalCount;

  /// Null means "all of the user's accounts merged".
  final int? selectedAccountId;

  bool get isEmpty => days.isEmpty;

  TransactionsState copyWith({
    List<TransactionDay>? days,
    TransactionFilter? filter,
    bool? isLoadingMore,
    bool? hasMore,
    int? totalCount,
    int? selectedAccountId,
    bool clearAccount = false,
  }) => TransactionsState(
    days: days ?? this.days,
    filter: filter ?? this.filter,
    isLoadingMore: isLoadingMore ?? this.isLoadingMore,
    hasMore: hasMore ?? this.hasMore,
    totalCount: totalCount ?? this.totalCount,
    selectedAccountId: clearAccount
        ? null
        : (selectedAccountId ?? this.selectedAccountId),
  );
}

/// Paginated, infinite-scroll transaction history.
///
/// One awkward shape has to be handled: the server paginates **per account**
/// (`/accounts/{id}/transactions/`) and there is no all-accounts endpoint. So for a
/// multi-vehicle holder viewing "all", the controller fetches page N of every account
/// and merges — which means `hasMore` is true while ANY account has more, and the
/// merged ordering is only correct within the pages fetched so far. It is the honest
/// best available: the alternative is forcing the user to pick a vehicle before they
/// can see any history at all.
///
/// Selecting a single account (the common case, and the default for a one-vehicle
/// holder) is exactly paginated with no merging.
class TransactionsController extends AsyncNotifier<TransactionsState> {
  /// The page size is the SERVER's default (`StandardPagination.page_size = 20`) and
  /// is deliberately not overridden — `?page_size=` caps at 100, and a bigger page on
  /// mobile data buys a longer first paint for rows nobody scrolls to.
  int _page = 1;
  final List<Transaction> _flat = [];

  @override
  Future<TransactionsState> build() async {
    final wallet = await ref.watch(walletControllerProvider.future);
    final accountIds = wallet.vehicles
        .map((v) => v.accountId)
        .whereType<int>()
        .toList(growable: false);

    _page = 1;
    _flat.clear();

    if (accountIds.isEmpty) {
      return const TransactionsState();
    }

    // A single-vehicle holder gets true pagination rather than the merge path.
    final selected = accountIds.length == 1 ? accountIds.first : null;
    return _loadPage(
      accountIds: accountIds,
      selectedAccountId: selected,
      filter: TransactionFilter.all,
      reset: true,
    );
  }

  Future<TransactionsState> _loadPage({
    required List<int> accountIds,
    required int? selectedAccountId,
    required TransactionFilter filter,
    required bool reset,
  }) async {
    final repository = ref.read(walletRepositoryProvider);
    final wallet = ref.read(walletControllerProvider).value;
    final plateFor = <int, String>{
      for (final vehicle in wallet?.vehicles ?? const <MyVehicle>[])
        if (vehicle.accountId != null) vehicle.accountId!: vehicle.plateNumber,
    };

    if (reset) {
      _page = 1;
      _flat.clear();
    }

    final targets = selectedAccountId == null
        ? accountIds
        : [selectedAccountId];

    var anyHasMore = false;
    var total = 0;

    for (final accountId in targets) {
      try {
        final page = await repository.transactions(
          accountId: accountId,
          page: _page,
          type: filter.type,
        );
        // Labelled with the account and plate so a merged feed can say which vehicle a
        // fare belongs to. The single-account list ignores these.
        _flat.addAll(
          page.items.map(
            (t) => t.copyWith(
              accountId: accountId,
              plateNumber: plateFor[accountId],
            ),
          ),
        );
        anyHasMore = anyHasMore || page.meta.hasMore;
        total += page.meta.count;
      } on NotFoundFailure {
        // An account that has since been transferred away. Skipped rather than failing
        // the whole list.
        continue;
      }
    }

    _flat.sort((a, b) {
      final aTime = a.processedAt;
      final bTime = b.processedAt;
      if (aTime == null || bTime == null) return 0;
      return bTime.compareTo(aTime);
    });

    return TransactionsState(
      days: _group(_flat),
      filter: filter,
      hasMore: anyHasMore,
      totalCount: total,
      selectedAccountId: selectedAccountId,
    );
  }

  /// Groups by PKT calendar day, preserving newest-first order.
  static List<TransactionDay> _group(List<Transaction> transactions) {
    final buckets = <DateTime, List<Transaction>>{};
    for (final transaction in transactions) {
      final at = transaction.processedAt;
      if (at == null) continue;
      buckets.putIfAbsent(AppDates.pktDayKey(at), () => []).add(transaction);
    }
    final days = buckets.keys.toList()..sort((a, b) => b.compareTo(a));
    return days
        .map((day) => TransactionDay(day: day, transactions: buckets[day]!))
        .toList(growable: false);
  }

  Future<void> setFilter(TransactionFilter filter) async {
    final current = state.value;
    if (current == null || current.filter == filter) return;
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(
      () => _loadPage(
        accountIds: _accountIds(),
        selectedAccountId: current.selectedAccountId,
        filter: filter,
        reset: true,
      ),
    );
  }

  Future<void> selectAccount(int? accountId) async {
    final current = state.value;
    if (current == null) return;
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(
      () => _loadPage(
        accountIds: _accountIds(),
        selectedAccountId: accountId,
        filter: current.filter,
        reset: true,
      ),
    );
  }

  /// Fetches the next page. Guarded against re-entry so a fast scroll cannot fire
  /// three overlapping fetches and interleave their results.
  Future<void> loadMore() async {
    final current = state.value;
    if (current == null || current.isLoadingMore || !current.hasMore) return;

    state = AsyncValue.data(current.copyWith(isLoadingMore: true));
    _page++;
    try {
      final next = await _loadPage(
        accountIds: _accountIds(),
        selectedAccountId: current.selectedAccountId,
        filter: current.filter,
        reset: false,
      );
      state = AsyncValue.data(next);
    } on AppFailure {
      // Roll the page back so a retry does not skip a page and leave a hole in the
      // history.
      _page--;
      state = AsyncValue.data(current.copyWith(isLoadingMore: false));
    }
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(build);
  }

  List<int> _accountIds() {
    final wallet = ref.read(walletControllerProvider).value;
    return (wallet?.vehicles ?? const [])
        .map((v) => v.accountId)
        .whereType<int>()
        .toList(growable: false);
  }
}

final transactionsControllerProvider =
    AsyncNotifierProvider<TransactionsController, TransactionsState>(
      TransactionsController.new,
    );

/// A single account's transactions, for the tag- and vehicle-detail screens.
final accountTransactionsProvider =
    FutureProvider.family<List<Transaction>, int>((ref, accountId) async {
      final repository = ref.watch(walletRepositoryProvider);
      final page = await repository.transactions(accountId: accountId);
      return page.items;
    });
