import 'package:decimal/decimal.dart';
import 'package:mtag_user_app/core/env/app_env.dart';

/// How ready a payment method actually is.
///
/// This enum exists because the honest answer for three of the four methods is "not
/// ready", and the app is required to say so rather than ship a button that does
/// nothing. Every method's availability is derived from what the BACKEND can do, not
/// from a wish list.
enum GatewayAvailability {
  /// Works end to end today.
  available,

  /// The UI and the seam exist; the backend does not. Rendered as "coming soon"
  /// with a real alternative, never as a tappable button that silently fails.
  comingSoon,

  /// Implemented but not configured in this build (a missing dart-define). The user
  /// is shown the fallback instructions, not an error.
  notConfigured,
}

/// What a gateway needs from the app to be presented.
class GatewayContext {
  const GatewayContext({
    required this.accountId,
    required this.plateNumber,
    this.tid,
  });

  final int accountId;
  final String plateNumber;

  /// The chip TID. Null when the backend's tag serializer does not expose it, in
  /// which case the JazzCash instructions are hidden rather than shown with a blank.
  final String? tid;
}

/// One way to add money.
///
/// The seam is deliberately thin: no gateway in this app "completes a payment".
/// The most a gateway does is hand the user somewhere to pay and hand the app a
/// pending id to poll. Confirmation always comes from a server read.
abstract interface class PaymentGateway {
  /// Stable id, used for analytics and for remembering the last choice.
  String get id;

  GatewayAvailability availabilityFor(GatewayContext context);

  /// Whether this method can accept an arbitrary amount from the app.
  ///
  /// False for the aggregator flow, where the customer types the amount into the
  /// JazzCash app — the app cannot pre-set it, and an amount field that has no
  /// effect on the actual payment is a lie.
  bool get acceptsAmountFromApp;

  /// Minimum, when this method has one. Rs. 100 for the app-initiated flow, from
  /// `InitiateTopupSerializer`.
  int? get minimumAmount;
}

/// **Flow A — the one that actually works end to end.**
///
/// The customer opens the *JazzCash* app, chooses M-Tag, and enters their TID.
/// JazzCash calls `POST /payments/jazzcash/inquiry/` (the server returns the
/// consumer's name, plate and balance), the customer pays, and JazzCash calls
/// `POST /payments/jazzcash/payment/`, which credits the account idempotently on
/// `jazzcash_txn_id`.
///
/// **This app is not in that loop at all.** It cannot initiate the payment, cannot
/// know the amount, and gets no callback. So it is treated as the PRIMARY path and
/// implemented as what it is: instructions, a big copyable TID, a deep link into
/// JazzCash, and then polling `/payments/history/` and `/accounts/vehicle/{id}/` to
/// reflect the credit when it lands.
///
/// Both webhooks are gateway->server. The app never calls them.
class JazzCashAggregatorGateway implements PaymentGateway {
  const JazzCashAggregatorGateway();

  @override
  String get id => 'jazzcash_aggregator';

  @override
  GatewayAvailability availabilityFor(GatewayContext context) =>
      // Without a TID there is nothing for the customer to type into JazzCash, so
      // the instructions would be unfollowable.
      (context.tid ?? '').isEmpty
      ? GatewayAvailability.notConfigured
      : GatewayAvailability.available;

  @override
  bool get acceptsAmountFromApp => false;

  @override
  int? get minimumAmount => null;

  /// The deep link into the JazzCash app, when one is configured.
  Uri? deepLink() {
    const scheme = AppEnv.jazzCashAppScheme;
    return scheme.isEmpty ? null : Uri.tryParse(scheme);
  }
}

/// **Flow B — app-initiated. Incomplete server-side.**
///
/// `POST /payments/topup/` creates a pending `TopupRequest` and returns `pp_*`
/// fields. What is missing:
///
///   * **no gateway checkout URL** in the response, so the app has nowhere to send
///     the payload;
///   * `pp_Password` is a merchant credential and is correctly stripped before the
///     response leaves the server, so the payload is not a complete JazzCash Hosted
///     Checkout form either;
///   * `JAZZCASH_VERIFY_HASH` is off with the hashing formula unconfirmed.
///
/// Therefore: if `MTAG_JAZZCASH_CHECKOUT_URL` is not set, this gateway reports
/// [GatewayAvailability.notConfigured] and **does not pretend**. The user gets the
/// pending top-up with a clear "waiting for payment confirmation" state plus the
/// Flow A instructions, which work.
///
/// When the URL IS configured, the redirect leg runs in an in-app WebView and the
/// return URL is intercepted — and the redirect is then used only as a signal to
/// start polling the server. It is never itself treated as proof of payment.
class JazzCashCheckoutGateway implements PaymentGateway {
  const JazzCashCheckoutGateway();

  @override
  String get id => 'jazzcash_checkout';

  @override
  GatewayAvailability availabilityFor(GatewayContext context) =>
      AppEnv.appInitiatedCheckoutConfigured
      ? GatewayAvailability.available
      : GatewayAvailability.notConfigured;

  @override
  bool get acceptsAmountFromApp => true;

  @override
  int? get minimumAmount => AppEnv.minimumTopupAmount;

  Uri? checkoutUrl() {
    const url = AppEnv.jazzCashCheckoutUrl;
    return url.isEmpty ? null : Uri.tryParse(url);
  }

  /// Whether a URL the WebView navigated to is the configured return URL.
  ///
  /// Prefix match on the configured `JAZZCASH_RETURN_URL`, which the server appends
  /// `?topup_id=…` to.
  bool isReturnUrl(Uri url) {
    const configured = AppEnv.jazzCashReturnUrl;
    if (configured.isEmpty) return false;
    return url.toString().startsWith(configured);
  }
}

/// **Easypaisa — no backend implementation whatsoever.**
///
/// There is no Easypaisa endpoint, no service, no model field. The seam and the UI
/// exist so that wiring it later is a one-class change, and the option renders as
/// coming soon with retailer instructions.
///
/// Deliberately NOT done: inventing an endpoint, or shipping a button that silently
/// does nothing. Both would be worse than the honest "not yet".
class EasypaisaGateway implements PaymentGateway {
  const EasypaisaGateway();

  @override
  String get id => 'easypaisa';

  @override
  GatewayAvailability availabilityFor(GatewayContext context) =>
      AppEnv.easypaisaEnabled
      // Even with the flag on there is nothing behind it; the flag exists for
      // whoever implements the backend, so they can reveal the flow without
      // editing this file.
      ? GatewayAvailability.notConfigured
      : GatewayAvailability.comingSoon;

  @override
  bool get acceptsAmountFromApp => true;

  @override
  int? get minimumAmount => AppEnv.minimumTopupAmount;
}

/// **Card — no backend implementation.** Same situation as Easypaisa.
class CardGateway implements PaymentGateway {
  const CardGateway();

  @override
  String get id => 'card';

  @override
  GatewayAvailability availabilityFor(GatewayContext context) =>
      AppEnv.cardEnabled
      ? GatewayAvailability.notConfigured
      : GatewayAvailability.comingSoon;

  @override
  bool get acceptsAmountFromApp => true;

  @override
  int? get minimumAmount => AppEnv.minimumTopupAmount;
}

/// **Cash at a booth.** Pure information, and always available.
///
/// An operator tops up by TID or plate (`/accounts/topup/cash/`, `IsOperator`) and
/// the POS prints a receipt. The app's job is to say where to go and what to bring;
/// it never calls that endpoint — it is operator surface.
class CashAtBoothGateway implements PaymentGateway {
  const CashAtBoothGateway();

  @override
  String get id => 'cash_at_booth';

  @override
  GatewayAvailability availabilityFor(GatewayContext context) =>
      GatewayAvailability.available;

  @override
  bool get acceptsAmountFromApp => false;

  @override
  int? get minimumAmount => null;
}

/// Presets for the amount step, plus custom.
///
/// The minimum is Rs. 100 (server-enforced), so there is no Rs. 50 preset to tempt a
/// user into a rejection.
abstract final class TopupPresets {
  static const List<int> amounts = [500, 1000, 2000, 5000];

  static Decimal asDecimal(int rupees) => Decimal.fromInt(rupees);
}

/// Every gateway, in the order they are offered.
///
/// The aggregator flow is FIRST because it is the one that works. Presenting the
/// app-initiated flow first would put an unconfigured path at the top of the most
/// valuable screen in the app.
const List<PaymentGateway> paymentGateways = [
  JazzCashAggregatorGateway(),
  JazzCashCheckoutGateway(),
  CashAtBoothGateway(),
  EasypaisaGateway(),
  CardGateway(),
];
