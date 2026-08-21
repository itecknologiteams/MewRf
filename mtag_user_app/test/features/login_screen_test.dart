import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/features/auth/presentation/phone_input.dart';

/// Pakistani phone handling.
///
/// The display form has spaces and the wire form must not, because the server stores
/// exactly what a booth operator typed and `authenticate()` matches `USERNAME_FIELD`
/// exactly. Sending `0300 123 4567` against a stored `03001234567` fails with "Invalid
/// phone number or password" — which the user reads as a wrong password and retries until
/// the 10/minute throttle locks them out.
void main() {
  group('PhoneInput.toApi', () {
    test('strips the display spaces', () {
      expect(PhoneInput.toApi('0300 123 4567'), '03001234567');
    });

    test('strips any other punctuation a user might paste', () {
      expect(PhoneInput.toApi('+92 (300) 123-4567'), '923001234567');
      expect(PhoneInput.toApi('0300-1234567'), '03001234567');
    });

    test('is idempotent on an already-clean number', () {
      expect(PhoneInput.toApi('03001234567'), '03001234567');
    });
  });

  group('PhoneInput.toDisplay', () {
    test('formats as 03XX XXX XXXX', () {
      expect(PhoneInput.toDisplay('03001234567'), '0300 123 4567');
    });

    test('formats partial input without inserting trailing separators', () {
      expect(PhoneInput.toDisplay('03'), '03');
      expect(PhoneInput.toDisplay('0300'), '0300');
      expect(PhoneInput.toDisplay('03001'), '0300 1');
      expect(PhoneInput.toDisplay('0300123'), '0300 123');
      expect(PhoneInput.toDisplay('03001234'), '0300 123 4');
    });

    test('round-trips through the wire form', () {
      expect(
        PhoneInput.toApi(PhoneInput.toDisplay('03211112222')),
        '03211112222',
      );
    });
  });

  group('PhoneInput.isValid', () {
    test('accepts an 11-digit 03 number, formatted or not', () {
      expect(PhoneInput.isValid('0300 123 4567'), isTrue);
      expect(PhoneInput.isValid('03001234567'), isTrue);
      expect(PhoneInput.isValid('03451234567'), isTrue);
    });

    test('rejects the wrong length', () {
      expect(PhoneInput.isValid('0300 123 456'), isFalse);
      expect(PhoneInput.isValid('0300 123 45678'), isFalse);
      expect(PhoneInput.isValid(''), isFalse);
    });

    test('rejects a number that does not start 03', () {
      expect(PhoneInput.isValid('04001234567'), isFalse);
      expect(PhoneInput.isValid('92300123456'), isFalse);
    });

    test('accepts any operator prefix, including ones that do not exist yet', () {
      // Validating the third digit against a list of known networks would reject numbers
      // on a network that launched after this build, and the cost of a wrong guess is a
      // user who cannot log in at all.
      for (final prefix in [
        '030',
        '031',
        '032',
        '033',
        '034',
        '035',
        '036',
        '037',
        '038',
        '039',
      ]) {
        expect(
          PhoneInput.isValid('${prefix}01234567'),
          isTrue,
          reason: '$prefix should be accepted',
        );
      }
    });
  });

  group('PakistaniPhoneFormatter', () {
    const formatter = PakistaniPhoneFormatter();

    TextEditingValue format(String oldText, String newText, {int? cursor}) =>
        formatter.formatEditUpdate(
          TextEditingValue(
            text: oldText,
            selection: TextSelection.collapsed(offset: oldText.length),
          ),
          TextEditingValue(
            text: newText,
            selection: TextSelection.collapsed(
              offset: cursor ?? newText.length,
            ),
          ),
        );

    test('inserts separators as the user types', () {
      expect(format('0300', '03001').text, '0300 1');
      expect(format('0300 123', '0300 1234').text, '0300 123 4');
    });

    test('refuses a twelfth digit rather than truncating silently', () {
      final result = format('0300 123 4567', '0300 123 45678');
      expect(result.text, '0300 123 4567');
    });

    test('keeps the caret in the middle when editing mid-number', () {
      // The classic phone-field bug is sending the caret to the end on every keystroke,
      // which makes a typo in the middle impossible to fix without clearing the field.
      // Cursor after the 6th typed digit: "0300 12|"
      final result = format('0300 13 4567', '0300 123 4567', cursor: 7);
      expect(result.text, '0300 123 4567');
      // 6 digits precede the caret, and the formatted string has one space among them.
      expect(result.selection.baseOffset, 7);
    });

    test('handles a full paste', () {
      expect(format('', '03001234567').text, '0300 123 4567');
    });
  });
}
