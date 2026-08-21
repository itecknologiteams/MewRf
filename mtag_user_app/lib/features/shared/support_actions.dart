import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:mtag_user_app/core/env/app_env.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';
import 'package:url_launcher/url_launcher.dart';

/// Dials support.
///
/// This is the account-recovery flow. There is no password-reset endpoint and no OTP
/// endpoint on the backend, so a forgotten password and a blocked account both end
/// here — which is why it is a real, prominent action rather than a footnote.
Future<void> callSupport(BuildContext context) async {
  final l10n = AppL10n.of(context);
  final uri = Uri(scheme: 'tel', path: AppEnv.supportPhone);
  final launched = await launchUrl(uri);
  if (!launched && context.mounted) {
    // A tablet or a device with no dialler. The number is put on the clipboard so the
    // user can still act on it.
    await Clipboard.setData(const ClipboardData(text: AppEnv.supportPhone));
    if (context.mounted) {
      showClaySnack(
        context,
        message: '${l10n.actionCopied}: ${AppEnv.supportPhoneDisplay}',
      );
    }
  }
}

/// Copies text and confirms it.
///
/// Used for the TID, which a user is copying in order to type it into another app —
/// so silent success is not enough; they need to know it worked before they switch
/// away.
Future<void> copyToClipboard(
  BuildContext context, {
  required String value,
  required String label,
}) async {
  await Clipboard.setData(ClipboardData(text: value));
  if (!context.mounted) return;
  final l10n = AppL10n.of(context);
  showClaySnack(
    context,
    message: '$label ${l10n.actionCopied.toLowerCase()}',
    tone: ClayTone.success,
  );
}
