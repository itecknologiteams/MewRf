import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mtag_user_app/core/data/auth_repository.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/core/router/app_router.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/onboarding/presentation/otp_controller.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Step 1: the number the booth registered.
///
/// Serves both flows. First-time setup and forgot-password ask the same question and run the
/// same three screens; what differs is [purpose], and one branch below.
class PhoneEntryScreen extends ConsumerStatefulWidget {
  const PhoneEntryScreen({
    this.purpose = OtpPurpose.passwordSetup,
    super.key,
  });

  final OtpPurpose purpose;

  bool get isReset => purpose == OtpPurpose.passwordReset;

  @override
  ConsumerState<PhoneEntryScreen> createState() => _PhoneEntryScreenState();
}

class _PhoneEntryScreenState extends ConsumerState<PhoneEntryScreen> {
  final _phone = TextEditingController();
  String? _error;
  bool _checking = false;

  /// Offers the login screen rather than silently redirecting: someone who believes they
  /// have no password needs to be told why they are being sent elsewhere.
  void _showAlreadyRegistered() {
    final l10n = AppL10n.of(context);
    showClaySheet<void>(
      context: context,
      builder: (sheetContext) => Padding(
        padding: const EdgeInsets.all(ClaySpace.gutter),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              l10n.phoneAlreadySetUpTitle,
              style: Theme.of(sheetContext).textTheme.titleLarge,
            ),
            const SizedBox(height: ClaySpace.md),
            Text(
              l10n.phoneAlreadySetUpBody,
              style: Theme.of(sheetContext).textTheme.bodyMedium,
            ),
            const SizedBox(height: ClaySpace.xl),
            ClayButton(
              label: l10n.phoneAlreadySetUpSignIn,
              icon: Icons.login_rounded,
              variant: ClayButtonVariant.primary,
              expand: true,
              onPressed: () {
                Navigator.of(sheetContext).pop();
                context.go(Routes.login);
              },
            ),
            const SizedBox(height: ClaySpace.md),
            ClayButton(
              label: l10n.actionCancel,
              variant: ClayButtonVariant.ghost,
              expand: true,
              onPressed: () => Navigator.of(sheetContext).pop(),
            ),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _phone.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final l10n = AppL10n.of(context);
    final digits = _phone.text.replaceAll(RegExp(r'\D'), '');
    // Pakistani mobile numbers are 11 digits starting 03.
    if (digits.length != 11 || !digits.startsWith('03')) {
      setState(() => _error = l10n.loginPhoneInvalid);
      return;
    }
    setState(() => _error = null);

    setState(() => _checking = true);

    // Ask what this number needs BEFORE sending anything. Someone who already has a
    // password does not need a verification code, and handing them one would be a dead end
    // — they would set a second password for no reason, or abandon the flow.
    final PhoneStatus status;
    try {
      status = await ref
          .read(authRepositoryProvider)
          .phoneStatus(phone: digits);
    } on Object catch (error) {
      if (!mounted) return;
      setState(() {
        _checking = false;
        _error = describeError(error, l10n);
      });
      return;
    }
    if (!mounted) return;
    setState(() => _checking = false);

    // The one branch that differs between the two flows.
    //
    // Setup is for accounts that have never had a password, so an account that HAS one is
    // sent to login instead. A reset is the opposite case by definition — diverting it the
    // same way would send the people who need it most straight back to the screen they
    // could not get past.
    if (status.hasPassword && !widget.isReset) {
      // Remembered so the login screen prefills the number they just typed rather than
      // asking for it again.
      await ref.read(secureStoreProvider).writeRememberedPhone(digits);
      if (!mounted) return;
      _showAlreadyRegistered();
      return;
    }

    // Someone who taps "Forgot password" for a number that never had one is not in an
    // error state — they are in the setup flow and do not know it. Quietly running setup
    // for them is right; the screens after this are identical either way.
    final purpose = widget.isReset && !status.hasPassword
        ? OtpPurpose.passwordSetup
        : widget.purpose;

    final controller = ref.read(otpFlowControllerProvider.notifier)
      ..start(phone: digits, purpose: purpose);
    final sent = await controller.requestCode();
    if (sent && mounted) {
      await context.push(Routes.otp);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final textTheme = Theme.of(context).textTheme;
    final flow = ref.watch(otpFlowControllerProvider);

    return ClayScaffold(
      showBack: true,
      body: ListView(
        children: [
          Text(
            widget.isReset ? l10n.resetPhoneTitle : l10n.phoneEntryTitle,
            style: textTheme.headlineMedium,
          ),
          const SizedBox(height: ClaySpace.sm),
          Text(
            widget.isReset ? l10n.resetPhoneBody : l10n.phoneEntryBody,
            style: textTheme.bodyMedium,
          ),
          const SizedBox(height: ClaySpace.xxl),

          ClayTextField(
            controller: _phone,
            label: l10n.loginPhoneLabel,
            hint: l10n.loginPhoneHint,
            keyboardType: TextInputType.phone,
            textInputAction: TextInputAction.done,
            autofocus: true,
            prefixIcon: Icons.phone_rounded,
            errorText: _error,
            maxLength: 11,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            autofillHints: const [AutofillHints.telephoneNumber],
            onSubmitted: (_) => _submit(),
          ),

          if (flow.error != null) ...[
            const SizedBox(height: ClaySpace.lg),
            ClayBanner(
              icon: Icons.info_outline_rounded,
              title: l10n.loginNoAccountTitle,
              message: describeError(flow.error!, l10n),
            ),
          ],

          const SizedBox(height: ClaySpace.xl),
          ClayButton(
            label: l10n.phoneEntryContinue,
            icon: Icons.sms_rounded,
            variant: ClayButtonVariant.primary,
            expand: true,
            loading: flow.busy || _checking,
            onPressed: flow.busy || _checking ? null : _submit,
          ),
        ],
      ),
    );
  }
}
