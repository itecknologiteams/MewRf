import 'package:flutter/services.dart';

/// Pakistani mobile-number handling.
///
/// The display form is `03XX XXX XXXX`, which is how everyone here writes and reads
/// a number. But the **server stores whatever the booth operator typed** — the portal
/// sends the number through unmodified, and there is no normalisation anywhere in
/// `RegisterSerializer` or on the `User.phone` column. `authenticate()` then matches
/// `USERNAME_FIELD` exactly.
///
/// So this file exists to hold one uncomfortable fact: the spaces the user sees must
/// NOT be sent. `03001234567` is what a booth types, and a login for
/// `0300 1234 567` would fail against it with "Invalid phone number or password" —
/// which the user would read as a wrong password and keep retrying until the 10/minute
/// throttle locked them out.
abstract final class PhoneInput {
  /// Digits only. What goes on the wire.
  static String toApi(String display) => display.replaceAll(RegExp(r'\D'), '');

  /// `03001234567` -> `0300 123 4567`.
  static String toDisplay(String raw) {
    final digits = toApi(raw);
    if (digits.length <= 4) return digits;
    if (digits.length <= 7) {
      return '${digits.substring(0, 4)} ${digits.substring(4)}';
    }
    final head = digits.substring(0, 4);
    final mid = digits.substring(4, 7);
    final tail = digits.substring(7, digits.length.clamp(0, 11));
    return '$head $mid $tail';
  }

  /// A plausible Pakistani mobile number: 11 digits starting `03`.
  ///
  /// Deliberately loose about the operator prefix. Validating the third digit against
  /// a list of known networks would reject numbers on a network that launched after
  /// this build, and the cost of a wrong guess is a user who cannot log in at all.
  static bool isValid(String display) {
    final digits = toApi(display);
    return digits.length == 11 && digits.startsWith('03');
  }
}

/// Formats as the user types, without fighting the cursor.
class PakistaniPhoneFormatter extends TextInputFormatter {
  const PakistaniPhoneFormatter();

  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    final digits = PhoneInput.toApi(newValue.text);
    if (digits.length > 11) return oldValue;

    final formatted = PhoneInput.toDisplay(digits);

    // The selection is recomputed by counting digits rather than characters. Setting
    // it to the end of the text would be simpler and would also send the caret to the
    // end every time someone edits the middle of their number — the classic phone-field
    // bug that makes a typo impossible to fix without clearing the whole field.
    final digitsBeforeCursor = PhoneInput.toApi(
      newValue.text.substring(
        0,
        newValue.selection.end.clamp(0, newValue.text.length),
      ),
    ).length;

    var offset = 0;
    var seen = 0;
    while (offset < formatted.length && seen < digitsBeforeCursor) {
      if (RegExp(r'\d').hasMatch(formatted[offset])) seen++;
      offset++;
    }

    return TextEditingValue(
      text: formatted,
      selection: TextSelection.collapsed(offset: offset),
    );
  }
}
