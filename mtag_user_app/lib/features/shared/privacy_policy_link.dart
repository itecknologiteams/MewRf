import 'package:flutter/material.dart';
import 'package:mtag_user_app/core/env/app_env.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';
import 'package:url_launcher/url_launcher.dart';

/// Opens the privacy policy, or explains plainly why it cannot be opened.
///
/// When [AppEnv.privacyPolicyUrl] is unset — the case on the LAN build, and until the
/// policy is actually published — this says so and offers the support number. It does NOT
/// hide the entry point: a user of a payment app is entitled to know a policy exists and
/// how to get it, and a link that opens a dead URL would be worse than one that explains
/// itself.
Future<void> openPrivacyPolicy(BuildContext context) async {
  final l10n = AppL10n.of(context);

  if (!AppEnv.hasPrivacyPolicy) {
    await showClaySheet<void>(
      context: context,
      builder: (sheetContext) => Padding(
        padding: const EdgeInsets.all(ClaySpace.gutter),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              l10n.privacyPolicy,
              style: Theme.of(sheetContext).textTheme.titleLarge,
            ),
            const SizedBox(height: ClaySpace.md),
            Text(
              l10n.privacyPolicyUnavailable(AppEnv.supportPhoneDisplay),
              style: Theme.of(sheetContext).textTheme.bodyMedium,
            ),
            const SizedBox(height: ClaySpace.xl),
            ClayButton(
              label: l10n.actionClose,
              expand: true,
              onPressed: () => Navigator.of(sheetContext).pop(),
            ),
          ],
        ),
      ),
    );
    return;
  }

  final uri = Uri.tryParse(AppEnv.privacyPolicyUrl);
  final opened =
      uri != null && await launchUrl(uri, mode: LaunchMode.externalApplication);
  if (!opened && context.mounted) {
    showClaySnack(
      context,
      message: l10n.privacyPolicyUnavailable(AppEnv.supportPhoneDisplay),
      tone: ClayTone.warning,
    );
  }
}

/// The Privacy Policy link, shown on the login screen.
///
/// A payment app should disclose where its policy is BEFORE sign-in, not only after —
/// someone deciding whether to hand over a phone number and a password should be able to
/// read it at that moment. Profile shows the same thing as a settings row, and both route
/// through [openPrivacyPolicy] so they cannot drift apart.
class PrivacyPolicyLink extends StatelessWidget {
  const PrivacyPolicyLink({this.centered = true, super.key});

  final bool centered;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final l10n = AppL10n.of(context);

    final link = GestureDetector(
      onTap: () => openPrivacyPolicy(context),
      behavior: HitTestBehavior.opaque,
      child: Padding(
        // Padding rather than a bare Text: an 11sp tappable line needs a real touch target.
        padding: const EdgeInsets.symmetric(
          vertical: ClaySpace.sm,
          horizontal: ClaySpace.xs,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.shield_outlined, size: 14, color: palette.textMuted),
            const SizedBox(width: ClaySpace.xs),
            Text(
              l10n.privacyPolicy,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                decoration: TextDecoration.underline,
                decorationColor: palette.textMuted,
              ),
            ),
          ],
        ),
      ),
    );

    return Semantics(
      link: true,
      child: centered ? Center(child: link) : link,
    );
  }
}
