import 'package:decimal/decimal.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:mtag_user_app/core/data/payment_repository.dart';
import 'package:mtag_user_app/core/errors/app_failure.dart';
import 'package:mtag_user_app/core/models/enums.dart';
import 'package:mtag_user_app/core/models/topup.dart';
import 'package:mtag_user_app/core/network/api_client.dart';
import 'package:mtag_user_app/features/topup/domain/payment_gateway.dart';

/// The top-up flow, including the two branches an optimistic implementation would skip.
///
/// The whole design rests on one rule — **a balance is only ever displayed from a server
/// read** — and on being honest that of the five payment methods, only one works end to
/// end today, and it is the one this app is not part of.
void main() {
  group('InitiateTopupResult', () {
    test('drops pp_Password even if an older server still sends it', () {
      // Defence in depth. The server now strips it (a merchant credential must never
      // reach a phone), but a booth running a previous build would still return it, and
      // it must not end up in app memory or a log.
      final result = InitiateTopupResult.fromApi({
        'topup_id': '42',
        'jazzcash_payload': {
          'pp_TxnRefNo': '42',
          'pp_Amount': '50000',
          'pp_TxnCurrency': 'PKR',
          'pp_MerchantID': 'MC00001',
          'pp_Password': 'super-secret',
          'pp_ReturnURL': 'https://example.test/return?topup_id=42',
          'pp_SecureHash': 'ABC123',
          'topup_id': '42',
        },
      });

      expect(result.gatewayFields.containsKey('pp_Password'), isFalse);
      expect(result.carriesNoMerchantSecret, isTrue);
      expect(result.gatewayFields.values.contains('super-secret'), isFalse);
      // The fields the client legitimately needs survive.
      expect(result.gatewayFields['pp_MerchantID'], 'MC00001');
      expect(result.gatewayFields['pp_Amount'], '50000');
    });

    test('parses topup_id whether the server sends a string or a number', () {
      // JazzCashService returns `str(topup.id)` though the column is an integer.
      expect(
        InitiateTopupResult.fromApi({
          'topup_id': '7',
          'jazzcash_payload': <String, Object?>{},
        }).topupId,
        7,
      );
      expect(
        InitiateTopupResult.fromApi({
          'topup_id': 7,
          'jazzcash_payload': <String, Object?>{},
        }).topupId,
        7,
      );
    });

    test(
      'the payload carries no checkout URL, which is why Flow B is incomplete',
      () {
        final result = InitiateTopupResult.fromApi({
          'topup_id': '42',
          'jazzcash_payload': {
            'pp_TxnRefNo': '42',
            'pp_ReturnURL': 'https://example.test/return?topup_id=42',
          },
        });

        // A return URL is not a checkout URL. There is nowhere in this payload that says
        // where the customer should be sent to pay.
        expect(
          result.gatewayFields.keys.any(
            (k) =>
                k.toLowerCase().contains('checkout') ||
                k.toLowerCase().contains('gatewayurl'),
          ),
          isFalse,
        );
      },
    );
  });

  group('gateway availability', () {
    const withTid = GatewayContext(
      accountId: 1,
      plateNumber: 'KDE1836',
      tid: 'E28011700000021234ABCD',
    );
    const withoutTid = GatewayContext(accountId: 1, plateNumber: 'KDE1836');

    test('the aggregator flow is available when a TID is known', () {
      expect(
        const JazzCashAggregatorGateway().availabilityFor(withTid),
        GatewayAvailability.available,
      );
    });

    test('without a TID the aggregator flow is unusable, not merely awkward', () {
      // The instructions say "type your TID into JazzCash". With no TID there is nothing
      // to type, so the block is hidden rather than shown with a blank field.
      expect(
        const JazzCashAggregatorGateway().availabilityFor(withoutTid),
        GatewayAvailability.notConfigured,
      );
    });

    test('the aggregator flow cannot take an amount from the app', () {
      // The customer enters the amount in JazzCash. An amount field here would have no
      // effect on the actual payment.
      expect(const JazzCashAggregatorGateway().acceptsAmountFromApp, isFalse);
    });

    test(
      'app-initiated checkout reports notConfigured without a checkout URL',
      () {
        // MTAG_JAZZCASH_CHECKOUT_URL is unset in a test binary, which is also its default
        // in every real build until someone supplies one.
        expect(
          const JazzCashCheckoutGateway().availabilityFor(withTid),
          GatewayAvailability.notConfigured,
        );
      },
    );

    test(
      'Easypaisa and card are comingSoon — no backend exists for either',
      () {
        expect(
          const EasypaisaGateway().availabilityFor(withTid),
          GatewayAvailability.comingSoon,
        );
        expect(
          const CardGateway().availabilityFor(withTid),
          GatewayAvailability.comingSoon,
        );
      },
    );

    test('cash at a booth is always available, TID or not', () {
      expect(
        const CashAtBoothGateway().availabilityFor(withoutTid),
        GatewayAvailability.available,
      );
    });

    test(
      'the aggregator flow is offered FIRST, because it is the one that works',
      () {
        expect(paymentGateways.first, isA<JazzCashAggregatorGateway>());
      },
    );

    test('no preset is below the Rs. 100 server minimum', () {
      // Offering an amount guaranteed to be rejected is a trap.
      expect(TopupPresets.amounts.every((a) => a >= 100), isTrue);
    });
  });

  group('watchTopup', () {
    late _FakePaymentApi api;

    setUp(_FakePaymentApi.reset);

    test('emits confirmed once the server reports success', () async {
      api = _FakePaymentApi(
        responses: [
          [_pending(1, '500.00')],
          [_pending(1, '500.00')],
          [_success(1, '500.00')],
        ],
      );

      final progress = await api.watch(topupId: 1).toList();

      expect(progress.whereType<TopupWaitingForConfirmation>(), isNotEmpty);
      final confirmed = progress.last;
      expect(confirmed, isA<TopupConfirmed>());
      // The amount comes from the SERVER's record, not from what the user typed.
      expect((confirmed as TopupConfirmed).amount, Decimal.parse('500.00'));
    });

    test('a server-reported failure ends the poll as failed', () async {
      api = _FakePaymentApi(
        responses: [
          [_failed(1, '500.00')],
        ],
      );
      final progress = await api.watch(topupId: 1).toList();
      expect(progress.last, isA<TopupFailed>());
    });

    test('TIMES OUT rather than failing when nothing ever settles', () async {
      // The branch that matters. The gateway callback is asynchronous and may still land,
      // so reporting a failure here would tell the user their money vanished — and they
      // would pay again.
      api = _FakePaymentApi(
        responses: List.generate(40, (_) => [_pending(1, '500.00')]),
      );

      final progress = await api.watch(topupId: 1).toList();

      expect(progress.last, isA<TopupTimedOut>());
      expect(progress.whereType<TopupFailed>(), isEmpty);
      expect((progress.last as TopupTimedOut).topupId, 1);
    });

    test('a dropped poll does not become a failed payment', () async {
      // Losing signal mid-poll is not evidence about the payment. The poll keeps going.
      api = _FakePaymentApi(
        responses: [
          [_pending(1, '500.00')],
          null, // network failure
          null,
          [_success(1, '500.00')],
        ],
      );

      final progress = await api.watch(topupId: 1).toList();
      expect(progress.last, isA<TopupConfirmed>());
    });

    test(
      'a topup id absent from history keeps polling rather than failing',
      () async {
        // Replication lag between the booth and master can briefly hide a just-created row.
        api = _FakePaymentApi(
          responses: [
            [],
            [_pending(1, '500.00')],
            [_success(1, '500.00')],
          ],
        );

        final progress = await api.watch(topupId: 1).toList();
        expect(progress.last, isA<TopupConfirmed>());
      },
    );

    test('a confirmed top-up never carries a locally computed balance', () async {
      api = _FakePaymentApi(
        responses: [
          [_success(1, '500.00')],
        ],
      );
      final progress = await api.watch(topupId: 1).toList();
      // watchTopup itself always yields newBalance: null — the balance is re-read from
      // /accounts/vehicle/{id}/ by the controller, never derived from old + amount.
      expect((progress.last as TopupConfirmed).newBalance, isNull);
    });
  });
}

TopupRequest _pending(int id, String amount) => TopupRequest(
  id: id,
  amount: Decimal.parse(amount),
  status: TopupStatus.pending,
);

TopupRequest _success(int id, String amount) => TopupRequest(
  id: id,
  amount: Decimal.parse(amount),
  status: TopupStatus.success,
);

TopupRequest _failed(int id, String amount) => TopupRequest(
  id: id,
  amount: Decimal.parse(amount),
  status: TopupStatus.failed,
);

/// Drives [PaymentRepository.watchTopup] against a scripted history, with the real
/// backoff replaced so a 3-minute timeout runs instantly.
class _FakePaymentApi {
  _FakePaymentApi({required this.responses});

  /// One entry per poll. `null` means the request failed.
  final List<List<TopupRequest>?> responses;

  int _index = 0;

  static void reset() {}

  Stream<TopupProgress> watch({required int topupId}) {
    final repository = _StubRepository(this);
    return repository.watchTopup(
      accountId: 1,
      topupId: topupId,
      amount: Decimal.parse('500.00'),
      // Compressed so the timeout branch is reachable in a test. The production values
      // are 2s→30s backoff over ~3 minutes.
      timeout: const Duration(milliseconds: 200),
      delay: (_) async {},
    );
  }

  List<TopupRequest> next() {
    final response = _index < responses.length ? responses[_index] : null;
    _index++;
    if (response == null) {
      throw const NetworkFailure(message: 'poll dropped');
    }
    return response;
  }
}

/// A [PaymentRepository] whose only real method is [topupHistory].
///
/// Subclassed rather than mocked so the ACTUAL `watchTopup` logic — the backoff, the
/// status switch, the timeout — is what runs. Mocking it would test the mock.
class _StubRepository extends PaymentRepository {
  _StubRepository(this._api) : super(client: _MockApiClient());

  final _FakePaymentApi _api;

  @override
  Future<List<TopupRequest>> topupHistory(int accountId) async => _api.next();
}

/// Never called: [_StubRepository] overrides the only method that touches the network.
///
/// A mocktail mock rather than a real [ApiClient] because ApiClient's constructor is
/// private (it is built asynchronously by `ApiClient.create`, which opens the cookie jar
/// on disk). Nothing in this test reaches it.
class _MockApiClient extends Mock implements ApiClient {}
