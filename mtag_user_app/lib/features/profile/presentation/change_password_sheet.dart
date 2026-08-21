import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Change password.
///
/// The 8-character minimum mirrors `ChangePasswordView`, which checks it server-side and
/// returns "New password must be at least 8 characters". Checked here so the user is not
/// bounced, with the server still the authority.
Future<void> showChangePasswordSheet(BuildContext context, WidgetRef ref) {
  return showClaySheet<void>(
    context: context,
    builder: (sheetContext) => const _ChangePasswordForm(),
  );
}

class _ChangePasswordForm extends ConsumerStatefulWidget {
  const _ChangePasswordForm();

  @override
  ConsumerState<_ChangePasswordForm> createState() =>
      _ChangePasswordFormState();
}

class _ChangePasswordFormState extends ConsumerState<_ChangePasswordForm> {
  final _current = TextEditingController();
  final _next = TextEditingController();
  final _confirm = TextEditingController();

  bool _busy = false;
  String? _currentError;
  String? _nextError;
  String? _confirmError;

  @override
  void dispose() {
    _current.dispose();
    _next.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final l10n = AppL10n.of(context);

    setState(() {
      _currentError = _current.text.isEmpty ? l10n.loginPasswordRequired : null;
      _nextError = _next.text.length < 8 ? l10n.profilePasswordTooShort : null;
      _confirmError = _confirm.text != _next.text
          ? l10n.profilePasswordMismatch
          : null;
    });

    if (_currentError != null || _nextError != null || _confirmError != null) {
      return;
    }

    setState(() => _busy = true);
    try {
      await ref
          .read(authRepositoryProvider)
          .changePassword(
            oldPassword: _current.text,
            newPassword: _next.text,
          );
      if (!mounted) return;
      Navigator.of(context).pop();
      showClaySnack(
        context,
        message: l10n.profilePasswordChanged,
        tone: ClayTone.success,
      );
    } on Object catch (error) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        // The server reports a wrong current password as a message rather than a field
        // error ("Current password is incorrect"), so it is attached to the field it
        // actually concerns.
        _currentError = describeError(error, AppL10n.of(context));
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          l10n.profileChangePassword,
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: ClaySpace.lg),
        ClayTextField(
          controller: _current,
          label: l10n.profileCurrentPassword,
          obscureText: true,
          errorText: _currentError,
          textInputAction: TextInputAction.next,
        ),
        const SizedBox(height: ClaySpace.lg),
        ClayTextField(
          controller: _next,
          label: l10n.profileNewPassword,
          obscureText: true,
          errorText: _nextError,
          textInputAction: TextInputAction.next,
        ),
        const SizedBox(height: ClaySpace.lg),
        ClayTextField(
          controller: _confirm,
          label: l10n.profileConfirmPassword,
          obscureText: true,
          errorText: _confirmError,
          textInputAction: TextInputAction.done,
          onSubmitted: (_) => _submit(),
        ),
        const SizedBox(height: ClaySpace.xl),
        ClayButton(
          label: l10n.actionSave,
          variant: ClayButtonVariant.primary,
          expand: true,
          loading: _busy,
          onPressed: _busy ? null : _submit,
        ),
        const SizedBox(height: ClaySpace.md),
        ClayButton(
          label: l10n.actionCancel,
          variant: ClayButtonVariant.ghost,
          expand: true,
          onPressed: () => Navigator.of(context).pop(),
        ),
      ],
    );
  }
}
