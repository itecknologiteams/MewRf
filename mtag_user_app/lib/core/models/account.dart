import 'package:decimal/decimal.dart';
import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/utils/app_dates.dart';
import 'package:mtag_user_app/core/utils/money.dart';

part 'account.freezed.dart';

/// `GET /accounts/vehicle/{vehicle_id}/` — `AccountSerializer`.
///
/// Note the id trap this shape sits on top of: the endpoint is keyed by
/// **vehicle** id, and the `id` it returns is the **account** id. Everything
/// downstream — `/accounts/{id}/transactions/`, `/payments/topup/`,
/// `/payments/history/{id}/` — wants the account id, while `/tolls/trips/{id}/`
/// wants the vehicle id. Both are ints and swapping them yields a plausible 404 or,
/// worse before the ownership fixes, someone else's data.
@freezed
abstract class Account with _$Account {
  const factory Account({
    required int id,
    required String plateNumber,
    required VehicleType vehicleType,
    required Decimal balance,
    int? vehicleId,
    DateTime? balanceUpdatedAt,
    DateTime? createdAt,
  }) = _Account;

  factory Account.fromApi(Map<String, dynamic> json) => Account(
    id: (json['id'] as num).toInt(),
    plateNumber: json['plate_number']?.toString() ?? '',
    vehicleType: VehicleType.parse(json['vehicle_type']),
    // Required here, unlike MyVehicle.balance: this endpoint exists to report a
    // balance, so a response without one is malformed rather than "unknown".
    balance: Money.parseOrZero(json['balance']),
    vehicleId: (json['vehicle_id'] as num?)?.toInt(),
    balanceUpdatedAt: AppDates.tryParseUtc(json['balance_updated_at']),
    createdAt: AppDates.tryParseUtc(json['created_at']),
  );
}

/// One row of `GET /accounts/{account_id}/transactions/` — `TransactionSerializer`.
@freezed
abstract class Transaction with _$Transaction {
  const factory Transaction({
    required int id,
    required TransactionType type,
    required Decimal amount,
    required TransactionStatus status,
    required TransactionSource source,
    DateTime? processedAt,
    Decimal? balanceBefore,
    Decimal? balanceAfter,
    String? tagSerial,
    String? referenceId,

    /// Set only when this row came from the merged summary feed, which labels each
    /// transaction with the account and plate it belongs to. Null on a
    /// single-account list, where the plate is already the screen's subject.
    int? accountId,
    String? plateNumber,
  }) = _Transaction;

  factory Transaction.fromApi(Map<String, dynamic> json) => Transaction(
    id: (json['id'] as num).toInt(),
    type: TransactionType.parse(json['transaction_type']),
    amount: Money.parseOrZero(json['amount']),
    status: TransactionStatus.parse(json['status']),
    // Nullable server-side — the operator top-up and the app-initiated
    // JazzCash callback both create transactions without a source — so absent
    // parses to `unknown` rather than failing.
    source: TransactionSource.parse(json['source']),
    processedAt: AppDates.tryParseUtc(json['processed_at']),
    balanceBefore: Money.tryParse(json['balance_before']),
    balanceAfter: Money.tryParse(json['balance_after']),
    tagSerial: json['tag_serial']?.toString(),
    referenceId: json['reference_id']?.toString(),
    accountId: (json['account_id'] as num?)?.toInt(),
    plateNumber: json['plate_number']?.toString(),
  );
}

extension TransactionX on Transaction {
  bool get isCredit => type.isCredit;

  /// Whether to show the "synced from booth" note.
  ///
  /// A booth can run offline and syncs every 30s, so this deduction may have
  /// reached the server minutes after the trip actually happened. Saying so is the
  /// difference between a history a driver trusts and one that looks late and
  /// therefore wrong.
  bool get wasSyncedFromBooth => source == TransactionSource.offlineExitSync;
}

/// `GET /accounts/my/summary/` — the dashboard in one call.
///
/// Optional on the server. If the endpoint 404s the client aggregates the same
/// numbers itself from `/vehicles/my/`; see [AccountSummary.fromVehicles].
@freezed
abstract class AccountSummary with _$AccountSummary {
  const factory AccountSummary({
    /// A SUM ACROSS WALLETS. Not a spendable balance — no plaza will accept it —
    /// and every screen that shows it labels it as a total across N tags.
    required Decimal totalBalance,
    required int accountCount,
    required int vehicleCount,
    required int tagCount,
    required Decimal monthTollTotal,
    required int monthTollCount,
    required List<Account> accounts,
    required List<Transaction> recentTransactions,

    /// True when the total was computed over a set that included a balance the app
    /// could not read. The figure is then a floor, not a total, and is marked
    /// "partial" — a total that reads too high is the one that tells someone they
    /// can enter when they cannot.
    @Default(false) bool isPartial,
    DateTime? generatedAt,
  }) = _AccountSummary;

  factory AccountSummary.fromApi(Map<String, dynamic> json) => AccountSummary(
    totalBalance: Money.parseOrZero(json['total_balance']),
    accountCount: (json['account_count'] as num?)?.toInt() ?? 0,
    vehicleCount: (json['vehicle_count'] as num?)?.toInt() ?? 0,
    tagCount: (json['tag_count'] as num?)?.toInt() ?? 0,
    monthTollTotal: Money.parseOrZero(json['month_toll_total']),
    monthTollCount: (json['month_toll_count'] as num?)?.toInt() ?? 0,
    accounts:
        (json['accounts'] as List?)
            ?.whereType<Map<String, dynamic>>()
            .map(Account.fromApi)
            .toList(growable: false) ??
        const [],
    recentTransactions:
        (json['recent_transactions'] as List?)
            ?.whereType<Map<String, dynamic>>()
            .map(Transaction.fromApi)
            .toList(growable: false) ??
        const [],
    generatedAt: AppDates.tryParseUtc(json['generated_at']),
  );
}
