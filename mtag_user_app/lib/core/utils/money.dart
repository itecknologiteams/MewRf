import 'package:decimal/decimal.dart';
import 'package:intl/intl.dart';

/// Money.
///
/// The server's `DecimalField` arrives as a JSON **string** — `"1250.00"`, not
/// `1250.0`. It is kept as a [Decimal] the whole way through, and `double` never
/// touches it.
///
/// That is not fastidiousness. `0.1 + 0.2 != 0.3` in binary floating point, and a
/// toll wallet sums per-vehicle balances for the dashboard total, subtracts a fare
/// to preview a balance, and compares against a Rs. 50 threshold that decides
/// whether a barrier opens. A total that renders as `Rs. 4,249.99` because three
/// balances were added as doubles is a support call, and a comparison that lands
/// on the wrong side of 50 is a driver stopped at a gate.
abstract final class Money {
  static final Decimal zero = Decimal.zero;

  /// Parses a server money string. Returns null on anything unparseable rather
  /// than defaulting to zero — "we do not know this balance" and "this balance is
  /// empty" must stay distinguishable all the way to the screen.
  static Decimal? tryParse(Object? raw) {
    if (raw == null) return null;
    if (raw is Decimal) return raw;
    final text = raw.toString().trim();
    if (text.isEmpty) return null;
    return Decimal.tryParse(text);
  }

  /// Parses, treating absence as zero. Only for values the server guarantees,
  /// such as a transaction `amount`.
  static Decimal parseOrZero(Object? raw) => tryParse(raw) ?? zero;

  /// `Decimal` -> the exact string the server expects back.
  ///
  /// Always two decimal places, matching `DecimalField(decimal_places=2)`. Sent as
  /// a string so it survives JSON encoding without a float round-trip.
  static String toApiString(Decimal value) =>
      value.round(scale: 2).toStringAsFixed(2);

  /// `Rs. 1,250` — the everyday display form.
  ///
  /// Whole rupees by default: paisa are never charged on this expressway (every
  /// notified fare is a whole number) and two decimal places on every figure adds
  /// noise to a screen whose loudest element is a balance. Paisa are shown only
  /// when they are actually non-zero, so a Rs. 1,250.50 refund is never silently
  /// rounded away.
  static String format(Decimal? value, {String locale = 'en'}) {
    if (value == null) return '—';
    final hasPaisa = value.round(scale: 2) != value.truncate();
    final pattern = hasPaisa ? '#,##0.00' : '#,##0';
    final formatter = NumberFormat(pattern, locale);
    return 'Rs. ${formatter.format(value.toDouble())}';
  }

  /// A signed amount, for a transaction row: `− Rs. 120` or `+ Rs. 1,000`.
  ///
  /// The sign uses U+2212 MINUS, not a hyphen: at 16sp a hyphen next to a digit
  /// reads as part of the number.
  static String formatSigned(
    Decimal? value, {
    required bool isCredit,
    String locale = 'en',
  }) {
    if (value == null) return '—';
    final magnitude = format(value.abs(), locale: locale);
    return isCredit ? '+ $magnitude' : '− $magnitude';
  }

  /// Digits only, no currency prefix — for a field the user types into.
  static String formatBare(Decimal? value, {String locale = 'en'}) {
    if (value == null) return '';
    final hasPaisa = value.round(scale: 2) != value.truncate();
    return NumberFormat(
      hasPaisa ? '#,##0.00' : '#,##0',
      locale,
    ).format(value.toDouble());
  }

  /// Sums a list of balances.
  ///
  /// Nulls are SKIPPED, not counted as zero, and [hadUnknown] reports whether any
  /// were. A dashboard total computed over a vehicle whose balance failed to load
  /// is wrong in the one direction that matters — too low is merely alarming, too
  /// high tells someone they can enter when they cannot — so the caller has to be
  /// able to say "partial".
  static ({Decimal total, bool hadUnknown}) sum(Iterable<Decimal?> values) {
    var total = zero;
    var hadUnknown = false;
    for (final value in values) {
      if (value == null) {
        hadUnknown = true;
      } else {
        total += value;
      }
    }
    return (total: total, hadUnknown: hadUnknown);
  }

  static Decimal fromInt(int rupees) => Decimal.fromInt(rupees);
}
