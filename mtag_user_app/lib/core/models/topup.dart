import 'package:decimal/decimal.dart';
import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/utils/app_dates.dart';
import 'package:mtag_user_app/core/utils/money.dart';

part 'topup.freezed.dart';

/// One row of `GET /payments/history/{account_id}/` — `TopupRequestSerializer`.
///
/// Polled to resolve a pending top-up. This — a server read showing the request has
/// left `pending` — is the ONLY thing the app accepts as evidence that money
/// arrived. A WebView redirect, a gateway "success" screen and a returning deep
/// link all prove that a browser was somewhere, not that an account was credited.
@freezed
abstract class TopupRequest with _$TopupRequest {
  const factory TopupRequest({
    required int id,
    required Decimal amount,
    required TopupStatus status,
    String? jazzCashTxnId,
    DateTime? requestedAt,
    DateTime? completedAt,
  }) = _TopupRequest;

  factory TopupRequest.fromApi(Map<String, dynamic> json) => TopupRequest(
    id: (json['id'] as num).toInt(),
    amount: Money.parseOrZero(json['amount']),
    status: TopupStatus.parse(json['status']),
    jazzCashTxnId: json['jazzcash_txn_id']?.toString(),
    requestedAt: AppDates.tryParseUtc(json['requested_at']),
    completedAt: AppDates.tryParseUtc(json['completed_at']),
  );
}

/// `POST /payments/topup/` — what the server hands back.
///
/// The `jazzcash_payload` is a bag of `pp_*` fields and, critically, **contains no
/// gateway checkout URL**. It is not a complete JazzCash Hosted Checkout form
/// either: `pp_Password` is a merchant credential and is stripped server-side
/// before the response leaves (it must never reach a phone). `JAZZCASH_VERIFY_HASH`
/// is also off with the hashing formula unconfirmed.
///
/// So this response is enough to create a **pending** top-up and nothing more. The
/// app's job with it is to be honest: record the pending request, poll for its
/// resolution, and show the aggregator instructions that actually work.
@freezed
abstract class InitiateTopupResult with _$InitiateTopupResult {
  const factory InitiateTopupResult({
    required int topupId,
    required Map<String, String> gatewayFields,
  }) = _InitiateTopupResult;

  factory InitiateTopupResult.fromApi(Map<String, dynamic> json) {
    final payload = json['jazzcash_payload'];
    return InitiateTopupResult(
      // Sent as a string by the server (`str(topup.id)`), though the column is an
      // integer — parsed either way.
      topupId: int.parse(json['topup_id'].toString()),
      gatewayFields: payload is Map
          ? {
              for (final entry in payload.entries)
                if (entry.key.toString() != 'pp_Password')
                  entry.key.toString(): entry.value?.toString() ?? '',
            }
          : const {},
    );
  }
}

extension InitiateTopupResultX on InitiateTopupResult {
  /// Belt and braces on the server-side strip: if an older backend is still
  /// returning `pp_Password`, it is dropped in [InitiateTopupResult.fromApi] and
  /// this asserts the invariant for tests.
  bool get carriesNoMerchantSecret => !gatewayFields.containsKey('pp_Password');
}

/// What a top-up attempt is doing, as one state.
///
/// `waitingForConfirmation` and `timedOut` are the two states that matter and the
/// two an optimistic implementation would skip. The app reaches them constantly:
/// the aggregator flow has no completion signal at all, and the app-initiated flow
/// has no checkout URL configured.
///
/// There is no `credited` state derived from anything but a server read. Nothing in
/// this app adds money to a displayed balance locally.
sealed class TopupProgress {
  const TopupProgress();
}

class TopupIdle extends TopupProgress {
  const TopupIdle();
}

class TopupSubmitting extends TopupProgress {
  const TopupSubmitting();
}

/// A pending request exists server-side; the app is polling for its resolution.
class TopupWaitingForConfirmation extends TopupProgress {
  const TopupWaitingForConfirmation({
    required this.topupId,
    required this.amount,
    required this.attempt,
  });

  final int topupId;
  final Decimal amount;

  /// Which poll this is, for the backoff.
  final int attempt;
}

/// The server confirmed it. The amount shown here came from the server's own
/// record of the top-up, not from what the user typed.
class TopupConfirmed extends TopupProgress {
  const TopupConfirmed({required this.amount, required this.newBalance});

  final Decimal amount;

  /// Re-read from `/accounts/vehicle/{id}/` after confirmation — never computed as
  /// old + amount.
  final Decimal? newBalance;
}

class TopupFailed extends TopupProgress {
  const TopupFailed({required this.reason});

  final String reason;
}

/// Polling gave up. The top-up may still land — the gateway callback is
/// asynchronous and the booth sync is not instant — so this is explicitly NOT a
/// failure. The user is told the balance will update on its own.
class TopupTimedOut extends TopupProgress {
  const TopupTimedOut({required this.topupId, required this.amount});

  final int topupId;
  final Decimal amount;
}
