import 'package:decimal/decimal.dart';
import 'package:mtag_user_app/core/env/app_env.dart';
import 'package:mtag_user_app/core/errors/app_failure.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/topup.dart';
import 'package:mtag_user_app/core/network/api_client.dart';
import 'package:mtag_user_app/core/utils/money.dart';

class PaymentRepository {
  PaymentRepository({required ApiClient client}) : _client = client;

  final ApiClient _client;

  /// Creates a **pending** top-up server-side.
  ///
  /// That is all it does. `/payments/topup/` writes a `TopupRequest` row and returns
  /// `pp_*` fields with no checkout URL, so calling this does not begin a payment —
  /// it records an intention. Nothing about the returned payload should be presented
  /// to the user as progress toward being charged.
  ///
  /// [idempotencyKey] is generated per ATTEMPT by the caller and sent as a header.
  /// The server does not currently read it — `InitiateTopupView` has no idempotency
  /// handling — so its real job today is client-side: the controller refuses to
  /// re-POST an intent whose key it has already used, which is what stops a Retry
  /// tap from orphaning a second pending row. The header is sent anyway so it starts
  /// working the moment the server honours it, with no client change.
  Future<InitiateTopupResult> initiateTopup({
    required int accountId,
    required Decimal amount,
    required String idempotencyKey,
  }) async {
    if (amount < Money.fromInt(AppEnv.minimumTopupAmount)) {
      // Checked client-side purely so the user is not bounced off a server
      // validation they could have been warned about. The server enforces it too,
      // in InitiateTopupSerializer AND JazzCashService.initiate_topup.
      throw const ValidationFailure(
        message: 'Minimum top-up amount is Rs.${AppEnv.minimumTopupAmount}',
        fieldErrors: {
          'amount': 'Minimum top-up amount is Rs.${AppEnv.minimumTopupAmount}',
        },
      );
    }

    final data = await _client.post<InitiateTopupResult>(
      'payments/topup/',
      body: {'account_id': accountId, 'amount': Money.toApiString(amount)},
      headers: {'Idempotency-Key': idempotencyKey},
      parse: (data) =>
          InitiateTopupResult.fromApi(data as Map<String, dynamic>),
    );

    if (data == null) {
      throw const MalformedResponseFailure(
        message: 'Top-up was initiated but returned no id',
      );
    }
    return data;
  }

  /// Top-up history for an account. The confirmation channel.
  Future<List<TopupRequest>> topupHistory(int accountId) =>
      _client.get<List<TopupRequest>>(
        'payments/history/$accountId/',
        parse: (data) => (data as List)
            .whereType<Map<String, dynamic>>()
            .map(TopupRequest.fromApi)
            .toList(growable: false),
      );

  /// Polls until [topupId] leaves `pending`.
  ///
  /// This is the only thing the app treats as proof that money arrived. Not the
  /// WebView redirect, not a gateway success page, not the user saying they paid —
  /// all of those happen in a browser and none of them is a credited account. The
  /// JazzCash callback is asynchronous and, in the aggregator flow, the app is not
  /// even in the loop.
  ///
  /// Backoff 2s -> 30s, giving up after [timeout] (~3 min). Giving up is NOT a
  /// failure: the callback may still land, so the caller renders "we'll update your
  /// balance automatically" rather than an error.
  Stream<TopupProgress> watchTopup({
    required int accountId,
    required int topupId,
    required Decimal amount,
    Duration timeout = const Duration(minutes: 3),
    Future<void> Function(Duration) delay = _wait,
  }) async* {
    final deadline = DateTime.now().add(timeout);
    var attempt = 0;
    var backoff = const Duration(seconds: 2);

    while (DateTime.now().isBefore(deadline)) {
      attempt++;
      yield TopupWaitingForConfirmation(
        topupId: topupId,
        amount: amount,
        attempt: attempt,
      );

      await delay(backoff);
      // 2, 4, 8, 16, 30, 30, … — capped so a three-minute wait is a handful of
      // requests rather than ninety.
      backoff = Duration(
        seconds: (backoff.inSeconds * 2).clamp(2, 30),
      );

      try {
        final history = await topupHistory(accountId);
        final match = history.where((t) => t.id == topupId).firstOrNull;
        if (match == null) continue;

        switch (match.status) {
          case TopupStatus.success:
            // The amount comes from the SERVER's record, not from what the user
            // typed — if the gateway settled a different figure, the server's is the
            // true one.
            yield TopupConfirmed(amount: match.amount, newBalance: null);
            return;
          case TopupStatus.failed:
            yield const TopupFailed(reason: 'The payment did not go through.');
            return;
          case TopupStatus.pending:
          case TopupStatus.unknown:
            continue;
        }
      } on AppFailure {
        // A dropped poll is not a failed payment. Keep trying until the deadline —
        // reporting failure here would tell someone their money vanished because
        // their signal did.
        continue;
      }
    }

    yield TopupTimedOut(topupId: topupId, amount: amount);
  }

  static Future<void> _wait(Duration duration) =>
      Future<void>.delayed(duration);
}
