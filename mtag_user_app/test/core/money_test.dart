import 'package:decimal/decimal.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/core/utils/money.dart';

/// Money is the thing this app exists to display, and it arrives as a string. These
/// tests exist because the failure mode of getting it wrong is not a crash — it is a
/// balance that is quietly off by a paisa, or a comparison that lands on the wrong side
/// of the Rs. 50 barrier threshold.
void main() {
  group('parsing', () {
    test('parses the server string form', () {
      expect(Money.tryParse('1250.00'), Decimal.parse('1250.00'));
      expect(Money.tryParse('0.50'), Decimal.parse('0.5'));
      expect(Money.tryParse('9999999.99'), Decimal.parse('9999999.99'));
    });

    test('null and unparseable stay null, and are NOT zero', () {
      // "We do not know this balance" and "this balance is empty" are different facts,
      // and the UI shows a dash for one and Rs. 0 for the other. Collapsing them would
      // tell someone with a load failure that their wallet is empty.
      expect(Money.tryParse(null), isNull);
      expect(Money.tryParse(''), isNull);
      expect(Money.tryParse('   '), isNull);
      expect(Money.tryParse('not money'), isNull);
    });

    test('parseOrZero is for fields the server guarantees', () {
      expect(Money.parseOrZero(null), Decimal.zero);
      expect(Money.parseOrZero('12.34'), Decimal.parse('12.34'));
    });

    test('arithmetic is exact where double would not be', () {
      // The whole reason Decimal is used. As doubles, 0.1 + 0.2 == 0.30000000000000004.
      final sum = Decimal.parse('0.1') + Decimal.parse('0.2');
      expect(sum, Decimal.parse('0.3'));
      expect(sum.toString(), '0.3');
    });

    test('summing three wallet balances is exact', () {
      final result = Money.sum([
        Decimal.parse('100.10'),
        Decimal.parse('200.20'),
        Decimal.parse('300.30'),
      ]);
      expect(result.total, Decimal.parse('600.60'));
      expect(result.hadUnknown, isFalse);
    });

    test(
      'a null balance in the sum is skipped and flagged, not counted as zero',
      () {
        // A total computed over an unreadable balance is a FLOOR. The flag is what lets
        // the dashboard label it "partial" — too high is the direction that tells someone
        // they can enter a plaza when they cannot.
        final result = Money.sum([
          Decimal.parse('100.00'),
          null,
          Decimal.parse('50.00'),
        ]);
        expect(result.total, Decimal.parse('150.00'));
        expect(result.hadUnknown, isTrue);
      },
    );

    test('an empty sum is zero and complete', () {
      final result = Money.sum(const []);
      expect(result.total, Decimal.zero);
      expect(result.hadUnknown, isFalse);
    });
  });

  group('formatting', () {
    test('whole rupees carry no decimal places', () {
      // Every notified fare on this expressway is a whole number, and ".00" on every
      // figure is noise on a screen whose loudest element is a balance.
      expect(Money.format(Decimal.parse('1250.00')), 'Rs. 1,250');
      expect(Money.format(Decimal.parse('50')), 'Rs. 50');
      expect(Money.format(Decimal.zero), 'Rs. 0');
    });

    test('paisa are shown when they are actually non-zero', () {
      // A Rs. 1,250.50 refund must not be silently rounded to Rs. 1,250.
      expect(Money.format(Decimal.parse('1250.50')), 'Rs. 1,250.50');
      expect(Money.format(Decimal.parse('0.05')), 'Rs. 0.05');
    });

    test('thousands are grouped', () {
      expect(Money.format(Decimal.parse('1234567')), 'Rs. 1,234,567');
    });

    test('null renders as a dash, never as a zero', () {
      expect(Money.format(null), '—');
    });

    test('signed amounts use a real minus sign, not a hyphen', () {
      // At 16sp a hyphen next to a digit reads as part of the number.
      expect(
        Money.formatSigned(Decimal.parse('120'), isCredit: false),
        '− Rs. 120',
      );
      expect(
        Money.formatSigned(Decimal.parse('1000'), isCredit: true),
        '+ Rs. 1,000',
      );
    });

    test(
      'a signed amount shows magnitude, so a negative input is not double-signed',
      () {
        expect(
          Money.formatSigned(Decimal.parse('-120'), isCredit: false),
          '− Rs. 120',
        );
      },
    );

    test('formatBare omits the currency for an input field', () {
      expect(Money.formatBare(Decimal.parse('2500')), '2,500');
      expect(Money.formatBare(null), '');
    });
  });

  group('toApiString', () {
    test(
      'always two decimal places, matching DecimalField(decimal_places=2)',
      () {
        expect(Money.toApiString(Decimal.parse('500')), '500.00');
        expect(Money.toApiString(Decimal.parse('500.5')), '500.50');
        expect(Money.toApiString(Decimal.parse('0.05')), '0.05');
      },
    );

    test(
      'rounds beyond two places rather than sending a value the server rejects',
      () {
        expect(Money.toApiString(Decimal.parse('100.005')), '100.01');
        expect(Money.toApiString(Decimal.parse('100.004')), '100.00');
      },
    );

    test('round-trips through the wire form without drift', () {
      for (final value in ['100.00', '1250.50', '0.01', '9999999.99']) {
        expect(Money.toApiString(Money.tryParse(value)!), value);
      }
    });
  });

  group('threshold comparisons', () {
    test('Rs. 49.99 is below the Rs. 50 entry minimum', () {
      // The comparison that decides whether the app warns a driver the barrier will not
      // open. As doubles this is the classic place a value at the boundary flips.
      expect(Decimal.parse('49.99') < Money.fromInt(50), isTrue);
      expect(Decimal.parse('50.00') < Money.fromInt(50), isFalse);
      expect(Decimal.parse('50.01') < Money.fromInt(50), isFalse);
    });

    test('Rs. 99.99 is below the Rs. 100 top-up minimum', () {
      expect(Decimal.parse('99.99') < Money.fromInt(100), isTrue);
      expect(Decimal.parse('100.00') < Money.fromInt(100), isFalse);
    });
  });
}
