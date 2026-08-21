import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/onboarding/presentation/otp_controller.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Step 3: choose a password. The server signs the user in on success, so there is no
/// login step after this — the router sees a live session and moves to the dashboard.
class SetPasswordScreen extends ConsumerStatefulWidget {
  const SetPasswordScreen({super.key});

  @override
  ConsumerState<SetPasswordScreen> createState() => _SetPasswordScreenState();
}

class _SetPasswordScreenState extends ConsumerState<SetPasswordScreen> {
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  String? _error;
  bool _obscure = true;

  @override
  void dispose() {
    _password.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final l10n = AppL10n.of(context);
    // Validated here as well as server-side: a round trip to be told the password is too
    // short is a round trip that did not need to happen.
    if (_password.text.length < 8) {
      setState(() => _error = l10n.setPasswordTooShort);
      return;
    }
    if (_password.text != _confirm.text) {
      setState(() => _error = l10n.setPasswordMismatch);
      return;
    }
    setState(() => _error = null);
    await ref
        .read(otpFlowControllerProvider.notifier)
        .setPassword(_password.text);
    // No navigation here: the session becomes live and the router redirects.
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final textTheme = Theme.of(context).textTheme;
    final flow = ref.watch(otpFlowControllerProvider);

    return ClayScaffold(
      body: ListView(
        children: [
          Text(l10n.setPasswordTitle, style: textTheme.headlineMedium),
          const SizedBox(height: ClaySpace.sm),
          Text(l10n.setPasswordBody, style: textTheme.bodyMedium),
          const SizedBox(height: ClaySpace.xxl),

          ClayTextField(
            controller: _password,
            label: l10n.setPasswordLabel,
            obscureText: _obscure,
            autofocus: true,
            prefixIcon: Icons.lock_outline_rounded,
            textInputAction: TextInputAction.next,
            autofillHints: const [AutofillHints.newPassword],
            suffix: ClayIconButton(
              icon: _obscure
                  ? Icons.visibility_rounded
                  : Icons.visibility_off_rounded,
              semanticLabel: l10n.setPasswordLabel,
              size: 38,
              iconSize: 17,
              onPressed: () => setState(() => _obscure = !_obscure),
            ),
          ),
          const SizedBox(height: ClaySpace.lg),
          ClayTextField(
            controller: _confirm,
            label: l10n.setPasswordConfirmLabel,
            obscureText: _obscure,
            prefixIcon: Icons.lock_outline_rounded,
            textInputAction: TextInputAction.done,
            errorText: _error,
            onSubmitted: (_) => _submit(),
          ),

          if (flow.error != null) ...[
            const SizedBox(height: ClaySpace.lg),
            ClayBanner(
              icon: Icons.error_outline_rounded,
              title: l10n.setPasswordTitle,
              message: describeError(flow.error!, l10n),
              tone: ClayTone.danger,
            ),
          ],

          const SizedBox(height: ClaySpace.xl),
          ClayButton(
            label: l10n.setPasswordSubmit,
            icon: Icons.check_rounded,
            variant: ClayButtonVariant.primary,
            expand: true,
            loading: flow.busy,
            onPressed: flow.busy ? null : _submit,
          ),
        ],
      ),
    );
  }
}
