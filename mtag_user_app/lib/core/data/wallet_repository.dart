import 'package:decimal/decimal.dart';
import 'package:mtag_user_app/core/cache/cache_database.dart';
import 'package:mtag_user_app/core/data/cached.dart';
import 'package:mtag_user_app/core/data/capabilities.dart';
import 'package:mtag_user_app/core/errors/app_failure.dart';
import 'package:mtag_user_app/core/models/account.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/vehicle.dart';
import 'package:mtag_user_app/core/network/api_client.dart';
import 'package:mtag_user_app/core/network/api_envelope.dart';
import 'package:mtag_user_app/core/utils/money.dart';

/// Vehicles, tags, balances and transactions — everything behind the wallet.
///
/// The one repository the dashboard, tags, vehicles and transactions screens all
/// read from, because they are all views onto the same ownership chain:
/// `User -> Vehicle -> (Tag, Account -> Transaction)`.
class WalletRepository {
  WalletRepository({
    required ApiClient client,
    required CacheDatabase cache,
    required BackendCapabilities capabilities,
  }) : _client = client,
       _cache = cache,
       _capabilities = capabilities;

  final ApiClient _client;
  final CacheDatabase _cache;
  final BackendCapabilities _capabilities;

  /// Everything the user owns. The app's bootstrap call.
  ///
  /// `GET /vehicles/` is `IsOperator`, so this is the ONLY way a consumer can
  /// enumerate their own vehicles. If `/vehicles/my/` is absent the fallback is
  /// genuinely degraded — see [_myVehiclesFallback] — which is why the endpoint is
  /// listed as blocking rather than nice-to-have.
  Future<Cached<List<MyVehicle>>> myVehicles({required int userId}) {
    return fetchWithCache<List<MyVehicle>>(
      cache: _cache,
      key: CacheKeys.myVehicles(userId),
      fetch: () async {
        if (!_capabilities.shouldTryMyVehicles) {
          return _myVehiclesFallback(userId: userId);
        }
        try {
          final vehicles = await _client.get<List<MyVehicle>>(
            'vehicles/my/',
            parse: (data) => (data as List)
                .whereType<Map<String, dynamic>>()
                .map(MyVehicle.fromApi)
                .toList(growable: false),
          );
          _capabilities.recordMyVehicles(present: true);
          return vehicles;
        } on AppFailure catch (failure) {
          if (!BackendCapabilities.indicatesMissingEndpoint(failure)) rethrow;
          _capabilities.recordMyVehicles(present: false);
          return _myVehiclesFallback(userId: userId);
        }
      },
      encode: (vehicles) => vehicles.map(_encodeVehicle).toList(),
      decode: (json) => (json as List)
          .whereType<Map<String, dynamic>>()
          .map(MyVehicle.fromApi)
          .toList(growable: false),
    );
  }

  /// The pre-Phase-0 fallback for enumerating vehicles.
  ///
  /// There is no honest way to do this well. Without `/vehicles/my/` the server
  /// offers a consumer no listing at all, so the only ids available are the ones
  /// already on disk from a previous run. A fresh install against an old backend
  /// therefore shows an empty state that says so, rather than an empty state
  /// implying the user owns nothing.
  Future<List<MyVehicle>> _myVehiclesFallback({required int userId}) async {
    final cached = await readCacheOnly<List<MyVehicle>>(
      cache: _cache,
      key: CacheKeys.myVehicles(userId),
      decode: (json) => (json as List)
          .whereType<Map<String, dynamic>>()
          .map(MyVehicle.fromApi)
          .toList(growable: false),
    );
    final known = cached?.value ?? const <MyVehicle>[];
    if (known.isEmpty) return const [];

    // Re-read each known vehicle so at least the balances are current.
    final refreshed = <MyVehicle>[];
    for (final vehicle in known) {
      try {
        final detail = await vehicleDetail(vehicle.id);
        final account = await accountForVehicle(vehicle.id);
        refreshed.add(
          MyVehicle(
            id: detail.id,
            plateNumber: detail.plateNumber,
            vehicleType: detail.vehicleType,
            status: detail.status,
            registeredAt: detail.registeredAt,
            tag: detail.tag,
            accountId: account?.id,
            balance: account?.balance,
            balanceUpdatedAt: account?.balanceUpdatedAt,
          ),
        );
      } on AppFailure {
        // A vehicle that has since been transferred away now 404s. Dropping it is
        // correct — it is no longer the user's.
        continue;
      }
    }
    return refreshed;
  }

  Future<VehicleDetail> vehicleDetail(int vehicleId) =>
      _client.get<VehicleDetail>(
        'vehicles/$vehicleId/',
        parse: (data) => VehicleDetail.fromApi(data as Map<String, dynamic>),
      );

  Future<VehicleDetail> vehicleByPlate(
    String plate,
  ) => _client.get<VehicleDetail>(
    // The server normalises the plate (`KDE-1836` -> `KDE1836`), but sending the
    // normalised form anyway keeps the URL stable and avoids a path segment with
    // a space in it.
    'vehicles/plate/${Uri.encodeComponent(_normalisePlate(plate))}/',
    parse: (data) => VehicleDetail.fromApi(data as Map<String, dynamic>),
  );

  static String _normalisePlate(String plate) =>
      plate.replaceAll(RegExp(r'[\s\-]'), '').toUpperCase();

  /// The wallet for a vehicle. **Keyed by vehicle id; returns the ACCOUNT id.**
  ///
  /// Returns null on 404, which is a real state: a vehicle can exist with no account
  /// row. Every other failure propagates.
  Future<Account?> accountForVehicle(int vehicleId) async {
    try {
      return await _client.get<Account>(
        'accounts/vehicle/$vehicleId/',
        parse: (data) => Account.fromApi(data as Map<String, dynamic>),
      );
    } on NotFoundFailure {
      return null;
    }
  }

  /// A cached balance read, for the screens that show one figure.
  Future<Cached<Account>> account(int vehicleId) => fetchWithCache<Account>(
    cache: _cache,
    key: CacheKeys.account(vehicleId),
    fetch: () async {
      final account = await accountForVehicle(vehicleId);
      if (account == null) {
        throw const NotFoundFailure(message: 'No account for this vehicle');
      }
      return account;
    },
    encode: _encodeAccount,
    decode: (json) => Account.fromApi(json as Map<String, dynamic>),
  );

  /// One page of transactions.
  ///
  /// Only page 1 is cached — it is what the app needs to open with content offline,
  /// and caching an infinite scroll would grow without bound on a phone.
  Future<PagedEnvelope<Transaction>> transactions({
    required int accountId,
    int page = 1,
    TransactionType? type,
  }) async {
    final result = await _client.getPaged<Transaction>(
      'accounts/$accountId/transactions/',
      parseItem: Transaction.fromApi,
      page: page,
      query: {
        // Filtered server-side rather than client-side: filtering a single page
        // locally would show "3 tolls" when the account has 200.
        if (type != null && type != TransactionType.unknown) 'type': type.value,
      },
    );

    if (page == 1 && type == null) {
      await _cache.write(
        CacheKeys.transactionsFirstPage(accountId),
        result.items.map(_encodeTransaction).toList(),
      );
    }
    return result;
  }

  Future<Cached<List<Transaction>>?> cachedFirstTransactionPage(
    int accountId,
  ) => readCacheOnly<List<Transaction>>(
    cache: _cache,
    key: CacheKeys.transactionsFirstPage(accountId),
    decode: (json) => (json as List)
        .whereType<Map<String, dynamic>>()
        .map(Transaction.fromApi)
        .toList(growable: false),
  );

  /// The dashboard summary.
  ///
  /// Tries `/accounts/my/summary/` and falls back to aggregating client-side. The
  /// fallback loses nothing but round trips, so its absence is not degradation —
  /// unlike `/vehicles/my/`.
  Future<Cached<AccountSummary>> summary({
    required int userId,
    required List<MyVehicle> vehicles,
  }) {
    return fetchWithCache<AccountSummary>(
      cache: _cache,
      key: CacheKeys.summary(userId),
      fetch: () async {
        if (_capabilities.shouldTrySummary) {
          try {
            final summary = await _client.get<AccountSummary>(
              'accounts/my/summary/',
              parse: (data) =>
                  AccountSummary.fromApi(data as Map<String, dynamic>),
            );
            _capabilities.recordSummary(present: true);
            return summary;
          } on AppFailure catch (failure) {
            if (!BackendCapabilities.indicatesMissingEndpoint(failure)) rethrow;
            _capabilities.recordSummary(present: false);
          }
        }
        return _summaryFallback(vehicles);
      },
      encode: _encodeSummary,
      decode: (json) => AccountSummary.fromApi(json as Map<String, dynamic>),
    );
  }

  /// Builds the summary from what the app already has, plus one transaction page
  /// per account.
  ///
  /// The month-to-date toll figure is computed from those pages only, so it is a
  /// LOWER BOUND for a heavy user whose first page does not reach the start of the
  /// month. It is surfaced as partial rather than presented as a total — quietly
  /// under-reporting a month's tolls is the kind of wrong number people budget on.
  Future<AccountSummary> _summaryFallback(List<MyVehicle> vehicles) async {
    final accounts = <Account>[];
    final recent = <Transaction>[];
    var sawFailure = false;

    for (final vehicle in vehicles) {
      final accountId = vehicle.accountId;
      if (accountId == null) continue;
      accounts.add(
        Account(
          id: accountId,
          plateNumber: vehicle.plateNumber,
          vehicleType: vehicle.vehicleType,
          balance: vehicle.balance ?? Money.zero,
          vehicleId: vehicle.id,
          balanceUpdatedAt: vehicle.balanceUpdatedAt,
        ),
      );
      try {
        final page = await transactions(accountId: accountId);
        recent.addAll(
          page.items.map(
            (t) => t.copyWith(
              accountId: accountId,
              plateNumber: vehicle.plateNumber,
            ),
          ),
        );
      } on AppFailure {
        sawFailure = true;
      }
    }

    recent.sort((a, b) {
      final aTime = a.processedAt;
      final bTime = b.processedAt;
      if (aTime == null || bTime == null) return 0;
      return bTime.compareTo(aTime);
    });

    final totals = Money.sum(vehicles.map((v) => v.balance));
    final monthStart = _pktMonthStartUtc();
    var monthTotal = Money.zero;
    var monthCount = 0;
    for (final txn in recent) {
      final at = txn.processedAt;
      if (at == null || at.isBefore(monthStart)) continue;
      if (txn.type != TransactionType.tollDeduction) continue;
      if (txn.status != TransactionStatus.success) continue;
      monthTotal += txn.amount;
      monthCount++;
    }

    return AccountSummary(
      totalBalance: totals.total,
      accountCount: accounts.length,
      vehicleCount: vehicles.length,
      tagCount: vehicles.where((v) => v.hasTag).length,
      monthTollTotal: monthTotal,
      monthTollCount: monthCount,
      accounts: accounts,
      recentTransactions: recent.take(10).toList(growable: false),
      // Partial when a balance was missing OR a transaction page failed OR the
      // month may extend past the single page fetched.
      isPartial:
          totals.hadUnknown ||
          sawFailure ||
          _mayHaveOlderThisMonth(recent, monthStart),
      generatedAt: DateTime.now().toUtc(),
    );
  }

  /// Whether the fetched pages might not reach the start of the month.
  ///
  /// True when the oldest transaction seen is still inside this month — meaning
  /// there could be more of it beyond page 1.
  static bool _mayHaveOlderThisMonth(
    List<Transaction> transactions,
    DateTime monthStart,
  ) {
    if (transactions.isEmpty) return false;
    final oldest = transactions.last.processedAt;
    return oldest != null && oldest.isAfter(monthStart);
  }

  /// Midnight on the 1st, Karachi time, as a UTC instant.
  static DateTime _pktMonthStartUtc() {
    final nowPkt = DateTime.now().toUtc().add(const Duration(hours: 5));
    final startPkt = DateTime.utc(nowPkt.year, nowPkt.month);
    return startPkt.subtract(const Duration(hours: 5));
  }

  // ── Cache encoding ─────────────────────────────────────────────────────────
  //
  // Written in the SERVER's wire shape — snake_case keys, money as strings, ISO
  // timestamps — so the same `fromApi` parser reads both a live response and a
  // cached one. A second, cache-only shape would be a second parser to keep in
  // step, and the one that drifted would be the one only reachable offline.

  static Map<String, Object?> _encodeVehicle(MyVehicle vehicle) => {
    'id': vehicle.id,
    'plate_number': vehicle.plateNumber,
    'vehicle_type': vehicle.vehicleType.value,
    'status': vehicle.status.value,
    'registered_at': vehicle.registeredAt?.toIso8601String(),
    'account_id': vehicle.accountId,
    'balance': vehicle.balance == null
        ? null
        : Money.toApiString(vehicle.balance!),
    'balance_updated_at': vehicle.balanceUpdatedAt?.toIso8601String(),
    'tag': vehicle.tag == null
        ? null
        : {
            'id': vehicle.tag!.id,
            'tag_serial': vehicle.tag!.tagSerial,
            'tid': vehicle.tag!.tid,
            'epc': vehicle.tag!.epc,
            'status': vehicle.tag!.status.value,
            'is_valid': vehicle.tag!.isValid,
            'expiry_date': vehicle.tag!.expiryDate?.toIso8601String(),
            'issued_at': vehicle.tag!.issuedAt?.toIso8601String(),
            'last_scanned_at': vehicle.tag!.lastScannedAt?.toIso8601String(),
          },
  };

  static Map<String, Object?> _encodeAccount(Account account) => {
    'id': account.id,
    'vehicle_id': account.vehicleId,
    'plate_number': account.plateNumber,
    'vehicle_type': account.vehicleType.value,
    'balance': Money.toApiString(account.balance),
    'balance_updated_at': account.balanceUpdatedAt?.toIso8601String(),
    'created_at': account.createdAt?.toIso8601String(),
  };

  static Map<String, Object?> _encodeTransaction(Transaction txn) => {
    'id': txn.id,
    'transaction_type': txn.type.value,
    'amount': Money.toApiString(txn.amount),
    'status': txn.status.value,
    'source': txn.source == TransactionSource.unknown ? null : txn.source.value,
    'balance_before': txn.balanceBefore == null
        ? null
        : Money.toApiString(txn.balanceBefore!),
    'balance_after': txn.balanceAfter == null
        ? null
        : Money.toApiString(txn.balanceAfter!),
    'tag_serial': txn.tagSerial,
    'reference_id': txn.referenceId,
    'processed_at': txn.processedAt?.toIso8601String(),
    'account_id': txn.accountId,
    'plate_number': txn.plateNumber,
  };

  static Map<String, Object?> _encodeSummary(AccountSummary summary) => {
    'total_balance': Money.toApiString(summary.totalBalance),
    'account_count': summary.accountCount,
    'vehicle_count': summary.vehicleCount,
    'tag_count': summary.tagCount,
    'month_toll_total': Money.toApiString(summary.monthTollTotal),
    'month_toll_count': summary.monthTollCount,
    'accounts': summary.accounts.map(_encodeAccount).toList(),
    'recent_transactions': summary.recentTransactions
        .map(_encodeTransaction)
        .toList(),
    'generated_at': summary.generatedAt?.toIso8601String(),
  };
}

/// A total that is explicitly a sum across wallets.
///
/// A named type rather than a bare [Decimal] so the label cannot be lost in
/// transit. There is no single user balance in this system — `Account` is OneToOne on
/// `Vehicle` — and a figure that reads as "your balance" when it is the sum of three
/// wallets that cannot be pooled is actively misleading at a barrier.
class WalletTotal {
  const WalletTotal({
    required this.total,
    required this.walletCount,
    required this.isPartial,
  });

  factory WalletTotal.fromVehicles(List<MyVehicle> vehicles) {
    final sum = Money.sum(vehicles.map((v) => v.balance));
    return WalletTotal(
      total: sum.total,
      walletCount: vehicles.where((v) => v.accountId != null).length,
      isPartial: sum.hadUnknown,
    );
  }

  final Decimal total;
  final int walletCount;

  /// At least one balance could not be read, so [total] is a floor.
  final bool isPartial;
}
