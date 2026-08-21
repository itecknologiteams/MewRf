import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mtag_user_app/core/env/app_env.dart';
import 'package:mtag_user_app/core/router/app_router.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/auth/presentation/login_controller.dart';
import 'package:mtag_user_app/features/auth/presentation/phone_input.dart';
import 'package:mtag_user_app/features/shared/privacy_policy_link.dart';
import 'package:mtag_user_app/features/shared/support_actions.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _phone = TextEditingController();
  final _password = TextEditingController();
  final _passwordFocus = FocusNode();

  bool _remember = true;
  bool _obscure = true;
  bool _prefilled = false;

  /// Local validation, shown only after a submit attempt.
  ///
  /// Validating on every keystroke would put "enter a valid Pakistani mobile number"
  /// under a field the user is halfway through typing.
  String? _localPhoneError;
  String? _localPasswordError;

  @override
  void dispose() {
    _phone.dispose();
    _password.dispose();
    _passwordFocus.dispose();
    super.dispose();
  }

  void _submit() {
    final l10n = AppL10n.of(context);
    final phone = _phone.text;

    setState(() {
      _localPhoneError = phone.trim().isEmpty
          ? l10n.loginPhoneRequired
          : (PhoneInput.isValid(phone) ? null : l10n.loginPhoneInvalid);
      _localPasswordError = _password.text.isEmpty
          ? l10n.loginPasswordRequired
          : null;
    });

    if (_localPhoneError != null || _localPasswordError != null) return;

    FocusScope.of(context).unfocus();
    ref
        .read(loginControllerProvider.notifier)
        .submit(
          // Digits only. The server stores exactly what a booth operator typed and
          // matches it exactly, so the display spaces must not go on the wire.
          phone: PhoneInput.toApi(phone),
          password: _password.text,
          rememberPhone: _remember,
        );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;
    final state = ref.watch(loginControllerProvider);

    // Prefill once, when the remembered number arrives from secure storage.
    final remembered = state.rememberedPhone;
    if (!_prefilled && remembered != null && _phone.text.isEmpty) {
      _phone.text = PhoneInput.toDisplay(remembered);
      _prefilled = true;
    }

    return Scaffold(
      backgroundColor: palette.base,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(
            horizontal: ClaySpace.gutter,
            vertical: ClaySpace.xl,
          ),
          child: AutofillGroup(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const SizedBox(height: ClaySpace.xl),
                Text(l10n.loginTitle, style: textTheme.headlineMedium),
                const SizedBox(height: ClaySpace.xs),
                Text(l10n.loginSubtitle, style: textTheme.bodyMedium),
                const SizedBox(height: ClaySpace.xxl),

                // A blocked account is a dead end: the form is hidden entirely rather
                // than left tappable, because another attempt cannot succeed and each
                // one spends the user's 10/minute throttle budget.
                if (state.isBlockedAccount)
                  _BlockedAccountCard(onCall: () => callSupport(context))
                else ...[
                  ClayTextField(
                    controller: _phone,
                    label: l10n.loginPhoneLabel,
                    hint: l10n.loginPhoneHint,
                    prefixIcon: Icons.phone_rounded,
                    keyboardType: TextInputType.phone,
                    textInputAction: TextInputAction.next,
                    autofillHints: const [AutofillHints.telephoneNumber],
                    inputFormatters: const [PakistaniPhoneFormatter()],
                    errorText: _localPhoneError ?? state.phoneError,
                    onChanged: (_) {
                      if (_localPhoneError != null) {
                        setState(() => _localPhoneError = null);
                      }
                      ref.read(loginControllerProvider.notifier).clearErrors();
                    },
                    onSubmitted: (_) => _passwordFocus.requestFocus(),
                  ),
                  const SizedBox(height: ClaySpace.lg),
                  ClayTextField(
                    controller: _password,
                    focusNode: _passwordFocus,
                    label: l10n.loginPasswordLabel,
                    hint: l10n.loginPasswordHint,
                    prefixIcon: Icons.lock_outline_rounded,
                    obscureText: _obscure,
                    textInputAction: TextInputAction.done,
                    autofillHints: const [AutofillHints.password],
                    errorText: _localPasswordError ?? state.passwordError,
                    suffix: ClayIconButton(
                      icon: _obscure
                          ? Icons.visibility_outlined
                          : Icons.visibility_off_outlined,
                      semanticLabel: _obscure
                          ? 'Show password'
                          : 'Hide password',
                      size: 34,
                      iconSize: 17,
                      onPressed: () => setState(() => _obscure = !_obscure),
                    ),
                    onChanged: (_) {
                      if (_localPasswordError != null) {
                        setState(() => _localPasswordError = null);
                      }
                      ref.read(loginControllerProvider.notifier).clearErrors();
                    },
                    onSubmitted: (_) => _submit(),
                  ),

                  // The credential error. Under the form, not under a field, because
                  // that is where the server puts it — `non_field_errors`.
                  if (state.formError != null && !state.isThrottled) ...[
                    const SizedBox(height: ClaySpace.lg),
                    ClayBanner(
                      icon: Icons.error_outline_rounded,
                      title: state.formError!,
                      tone: ClayTone.danger,
                    ),
                  ],

                  if (state.isThrottled) ...[
                    const SizedBox(height: ClaySpace.lg),
                    ClayBanner(
                      icon: Icons.timer_outlined,
                      title: l10n.loginThrottledTitle,
                      message: l10n.loginThrottledBody(state.cooldownSeconds),
                    ),
                  ] else if (state.failure != null &&
                      state.formError == null) ...[
                    const SizedBox(height: ClaySpace.lg),
                    ClayBanner(
                      icon: Icons.cloud_off_rounded,
                      title: state.failure!.label(l10n),
                      tone: ClayTone.danger,
                    ),
                  ],

                  const SizedBox(height: ClaySpace.lg),
                  _RememberToggle(
                    value: _remember,
                    onChanged: (value) => setState(() => _remember = value),
                    label: l10n.loginRememberPhone,
                  ),
                  const SizedBox(height: ClaySpace.xl),
                  ClayButton(
                    label: state.isThrottled
                        ? l10n.loginThrottledBody(state.cooldownSeconds)
                        : l10n.loginSubmit,
                    variant: ClayButtonVariant.primary,
                    expand: true,
                    loading: state.isSubmitting,
                    onPressed: state.canSubmit ? _submit : null,
                  ),
                  const SizedBox(height: ClaySpace.lg),
                  ClayButton(
                    label: l10n.loginForgotPassword,
                    variant: ClayButtonVariant.ghost,
                    expand: true,
                    onPressed: () => _showForgotPassword(context),
                  ),
                ],

                const SizedBox(height: ClaySpace.xxl),

                // Registration is gated OFF, so this is information rather than a
                // link. `/auth/register/` has no phone verification, and the backend
                // now refuses anonymous registration outright — real accounts are
                // created at a booth. A Sign Up button here would lead nowhere.
                if (!AppEnv.registrationEnabled)
                  ClayCard(
                    depth: ClayDepth.control,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(
                              Icons.info_outline_rounded,
                              size: 18,
                              color: palette.textMuted,
                            ),
                            const SizedBox(width: ClaySpace.sm),
                            Expanded(
                              child: Text(
                                l10n.loginNoAccountTitle,
                                style: textTheme.titleMedium,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: ClaySpace.sm),
                        Text(
                          l10n.loginNoAccountBody,
                          style: textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),

                const SizedBox(height: ClaySpace.lg),
                // Disclosed BEFORE sign-in, not only after. Someone deciding whether to
                // hand over a phone number and password to a payment app should be able to
                // read the policy at that moment.
                const PrivacyPolicyLink(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// The recovery path.
  ///
  /// Now a real reset: `/auth/otp/request/` with `purpose=password_reset` proves the caller
  /// holds the registered number and lets them choose a new password. Completing it also
  /// revokes every other session, because the usual reason to reset is believing somebody
  /// else is in the account.
  ///
  /// The support number stays as the second option rather than being dropped — a code sent
  /// to a SIM you no longer have is no help, and that is exactly when a person needs to
  /// speak to someone.
  void _showForgotPassword(BuildContext context) {
    final l10n = AppL10n.of(context);
    showClaySheet<void>(
      context: context,
      builder: (sheetContext) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            l10n.loginForgotPassword,
            style: Theme.of(sheetContext).textTheme.titleLarge,
          ),
          const SizedBox(height: ClaySpace.md),
          Text(
            l10n.loginForgotPasswordBody(AppEnv.supportPhoneDisplay),
            style: Theme.of(sheetContext).textTheme.bodyMedium,
          ),
          const SizedBox(height: ClaySpace.xl),
          // Primary, because it is the one the holder can complete themselves.
          ClayButton(
            label: l10n.loginForgotPasswordReset,
            icon: Icons.lock_reset_rounded,
            variant: ClayButtonVariant.primary,
            expand: true,
            onPressed: () {
              Navigator.of(sheetContext).pop();
              context.push(Routes.forgotPassword);
            },
          ),
          const SizedBox(height: ClaySpace.md),
          ClayButton(
            label: l10n.actionCallSupport,
            icon: Icons.call_rounded,
            variant: ClayButtonVariant.ghost,
            expand: true,
            onPressed: () {
              Navigator.of(sheetContext).pop();
              callSupport(context);
            },
          ),
          const SizedBox(height: ClaySpace.md),
          ClayButton(
            label: l10n.actionClose,
            variant: ClayButtonVariant.ghost,
            expand: true,
            onPressed: () => Navigator.of(sheetContext).pop(),
          ),
        ],
      ),
    );
  }
}

class _BlockedAccountCard extends StatelessWidget {
  const _BlockedAccountCard({required this.onCall});

  final VoidCallback onCall;

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ClayBanner(
          icon: Icons.gpp_bad_outlined,
          title: l10n.loginBlockedTitle,
          message: l10n.loginBlockedBody(AppEnv.supportPhoneDisplay),
          tone: ClayTone.danger,
        ),
        const SizedBox(height: ClaySpace.xl),
        ClayButton(
          label: l10n.actionCallSupport,
          icon: Icons.call_rounded,
          variant: ClayButtonVariant.primary,
          expand: true,
          onPressed: onCall,
        ),
      ],
    );
  }
}

/// A clay switch: a pressed track with a raised knob.
class _RememberToggle extends StatelessWidget {
  const _RememberToggle({
    required this.value,
    required this.onChanged,
    required this.label,
  });

  final bool value;
  final ValueChanged<bool> onChanged;
  final String label;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    return Semantics(
      toggled: value,
      label: label,
      child: GestureDetector(
        onTap: () => onChanged(!value),
        behavior: HitTestBehavior.opaque,
        child: Row(
          children: [
            ClaySurface(
              style: ClayDepthStyle.pressed,
              depth: ClayDepth.nested,
              radius: ClayRadius.pill,
              width: 46,
              height: 26,
              child: AnimatedAlign(
                duration: clayPressDuration(context),
                alignment: value ? Alignment.centerRight : Alignment.centerLeft,
                child: Padding(
                  padding: const EdgeInsets.all(3),
                  child: ClaySurface(
                    depth: ClayDepth.nested,
                    radius: ClayRadius.pill,
                    width: 20,
                    height: 20,
                    color: value ? palette.primary : palette.surface,
                  ),
                ),
              ),
            ),
            const SizedBox(width: ClaySpace.md),
            Expanded(
              child: Text(label, style: Theme.of(context).textTheme.bodyMedium),
            ),
          ],
        ),
      ),
    );
  }
}
