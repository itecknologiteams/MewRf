import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mtag_user_app/core/env/app_env.dart';
import 'package:mtag_user_app/core/providers.dart';
import 'package:mtag_user_app/core/router/app_router.dart';
import 'package:mtag_user_app/core/settings/app_settings.dart';
import 'package:mtag_user_app/core/utils/labels.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/auth/presentation/phone_input.dart';
import 'package:mtag_user_app/features/auth/presentation/session_controller.dart';
import 'package:mtag_user_app/features/profile/presentation/biometric_lock.dart';
import 'package:mtag_user_app/features/profile/presentation/change_password_sheet.dart';
import 'package:mtag_user_app/features/shared/detail_row.dart';
import 'package:mtag_user_app/features/shared/privacy_policy_link.dart';
import 'package:mtag_user_app/features/shared/support_actions.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';
import 'package:package_info_plus/package_info_plus.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;
    final user = ref.watch(currentUserProvider);
    final settings = ref.watch(appSettingsProvider);

    return Scaffold(
      backgroundColor: palette.base,
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.only(
            left: ClaySpace.gutter,
            right: ClaySpace.gutter,
            top: ClaySpace.lg,
            bottom: ClaySpace.xl,
          ),
          children: [
            Text(l10n.profileTitle, style: textTheme.headlineMedium),
            const SizedBox(height: ClaySpace.xl),

            ClayCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      ClaySurface(
                        style: ClayDepthStyle.pressed,
                        depth: ClayDepth.control,
                        radius: ClayRadius.pill,
                        width: 58,
                        height: 58,
                        child: Center(
                          child: Text(
                            _initials(user?.fullName ?? ''),
                            style: textTheme.titleLarge?.copyWith(
                              color: palette.primaryOnSurface,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: ClaySpace.lg),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              user?.fullName ?? l10n.unknownValue,
                              style: textTheme.titleLarge,
                              maxLines: 2,
                            ),
                            const SizedBox(height: 2),
                            Text(
                              PhoneInput.toDisplay(user?.phone ?? ''),
                              style: textTheme.bodySmall,
                              textDirection: TextDirection.ltr,
                            ),
                          ],
                        ),
                      ),
                      ClayIconButton(
                        icon: Icons.edit_outlined,
                        semanticLabel: l10n.profileEditName,
                        size: 38,
                        iconSize: 17,
                        onPressed: () => _editName(context, ref),
                      ),
                    ],
                  ),
                  const SizedBox(height: ClaySpace.lg),
                  DetailRow(
                    label: l10n.profileCnic,
                    value: user?.cnic ?? l10n.profileNotProvided,
                    monospace: user?.cnic != null,
                  ),
                  const SizedBox(height: ClaySpace.sm),
                  Text(
                    // Only `full_name` and `cnic` are editable, and the server enforces
                    // that too — `phone` is the USERNAME_FIELD and `user_role`/`status`
                    // are staff-only. Saying so here prevents a support call about a
                    // field the app appears to be missing.
                    l10n.profilePhoneChangeNote,
                    style: textTheme.bodySmall,
                  ),
                ],
              ),
            ),
            const SizedBox(height: ClaySpace.cardGap),

            _SettingsGroup(
              title: l10n.profileAppearance,
              children: [
                _ChoiceRow(
                  label: l10n.profileThemeSystem,
                  selected: settings.themeMode == ThemeMode.system,
                  onTap: () => ref
                      .read(appSettingsProvider.notifier)
                      .setThemeMode(ThemeMode.system),
                ),
                _ChoiceRow(
                  label: l10n.profileThemeLight,
                  selected: settings.themeMode == ThemeMode.light,
                  onTap: () => ref
                      .read(appSettingsProvider.notifier)
                      .setThemeMode(ThemeMode.light),
                ),
                _ChoiceRow(
                  label: l10n.profileThemeDark,
                  selected: settings.themeMode == ThemeMode.dark,
                  onTap: () => ref
                      .read(appSettingsProvider.notifier)
                      .setThemeMode(ThemeMode.dark),
                ),
              ],
            ),
            const SizedBox(height: ClaySpace.cardGap),

            _SettingsGroup(
              title: l10n.profileLanguage,
              children: [
                _ChoiceRow(
                  label: l10n.profileThemeSystem,
                  selected: settings.locale == null,
                  onTap: () =>
                      ref.read(appSettingsProvider.notifier).setLocale(null),
                ),
                _ChoiceRow(
                  label: l10n.profileLanguageEnglish,
                  selected: settings.locale?.languageCode == 'en',
                  onTap: () => ref
                      .read(appSettingsProvider.notifier)
                      .setLocale(const Locale('en')),
                ),
                _ChoiceRow(
                  // The Urdu option is labelled in Urdu. Someone looking for it cannot
                  // necessarily read "Urdu".
                  label: l10n.profileLanguageUrdu,
                  selected: settings.locale?.languageCode == 'ur',
                  onTap: () => ref
                      .read(appSettingsProvider.notifier)
                      .setLocale(const Locale('ur')),
                ),
              ],
            ),
            const SizedBox(height: ClaySpace.cardGap),

            const BiometricLockCard(),
            const SizedBox(height: ClaySpace.cardGap),

            _SettingsGroup(
              title: l10n.profileSecurity,
              children: [
                _ActionRow(
                  icon: Icons.password_rounded,
                  label: l10n.profileChangePassword,
                  onTap: () => showChangePasswordSheet(context, ref),
                ),
              ],
            ),
            const SizedBox(height: ClaySpace.cardGap),

            _SettingsGroup(
              title: l10n.profileSupport,
              children: [
                _ActionRow(
                  icon: Icons.call_rounded,
                  label: l10n.profileSupportPhone(AppEnv.supportPhoneDisplay),
                  onTap: () => callSupport(context),
                ),
                _ActionRow(
                  icon: Icons.price_change_outlined,
                  label: l10n.faresTitle,
                  onTap: () => context.push(Routes.fares),
                ),
                // The same link as the login screen, so a user who has already signed in
                // can still find the policy.
                _ActionRow(
                  icon: Icons.shield_outlined,
                  label: l10n.privacyPolicy,
                  onTap: () => openPrivacyPolicy(context),
                ),
              ],
            ),
            const SizedBox(height: ClaySpace.cardGap),

            ClayButton(
              label: l10n.profileSignOut,
              icon: Icons.logout_rounded,
              variant: ClayButtonVariant.danger,
              expand: true,
              onPressed: () => _confirmSignOut(context, ref),
            ),
            const SizedBox(height: ClaySpace.lg),

            const _VersionLine(),
          ],
        ),
      ),
    );
  }

  static String _initials(String fullName) {
    final parts = fullName
        .trim()
        .split(RegExp(r'\s+'))
        .where((p) => p.isNotEmpty);
    if (parts.isEmpty) return '—';
    if (parts.length == 1) return parts.first.characters.first.toUpperCase();
    return '${parts.first.characters.first}${parts.last.characters.first}'
        .toUpperCase();
  }

  /// Log out asks first — it is not destructive, but signing back in needs a password
  /// this app cannot help with if it has been forgotten.
  Future<void> _confirmSignOut(BuildContext context, WidgetRef ref) async {
    final l10n = AppL10n.of(context);
    final confirmed = await showClaySheet<bool>(
      context: context,
      builder: (sheetContext) => Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            l10n.profileSignOutConfirmTitle,
            style: Theme.of(sheetContext).textTheme.titleLarge,
          ),
          const SizedBox(height: ClaySpace.md),
          Text(
            l10n.profileSignOutConfirmBody,
            style: Theme.of(sheetContext).textTheme.bodyMedium,
          ),
          const SizedBox(height: ClaySpace.xl),
          ClayButton(
            label: l10n.profileSignOut,
            variant: ClayButtonVariant.danger,
            expand: true,
            onPressed: () => Navigator.of(sheetContext).pop(true),
          ),
          const SizedBox(height: ClaySpace.md),
          ClayButton(
            label: l10n.actionCancel,
            variant: ClayButtonVariant.ghost,
            expand: true,
            onPressed: () => Navigator.of(sheetContext).pop(false),
          ),
        ],
      ),
    );

    if (confirmed ?? false) {
      await ref.read(sessionControllerProvider.notifier).signOut();
    }
  }

  Future<void> _editName(BuildContext context, WidgetRef ref) async {
    final l10n = AppL10n.of(context);
    final user = ref.read(currentUserProvider);

    // The sheet owns its TextEditingController (see _EditNameSheet).
    //
    // It used to be created here and disposed as soon as showClaySheet returned — but
    // that future completes the moment pop() is called, while the sheet's EditableText
    // stays MOUNTED for the ~250ms exit animation. Disposing its controller underneath
    // it corrupts the element teardown, which surfaces as
    // `'_dependents.isEmpty': is not true` with nothing pointing at this sheet.
    final name = await showClaySheet<String>(
      context: context,
      builder: (sheetContext) =>
          _EditNameSheet(initialName: user?.fullName ?? ''),
    );

    if (name == null || name.isEmpty || !context.mounted) return;

    try {
      await ref.read(authRepositoryProvider).updateProfile(fullName: name);
      await ref.read(sessionControllerProvider.notifier).refreshUser();
      if (context.mounted) {
        showClaySnack(
          context,
          message: l10n.profileNameUpdated,
          tone: ClayTone.success,
        );
      }
    } on Object catch (error) {
      if (context.mounted) {
        showClaySnack(
          context,
          message: describeError(error, l10n),
          tone: ClayTone.danger,
        );
      }
    }
  }
}

class _SettingsGroup extends StatelessWidget {
  const _SettingsGroup({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return ClayCard(
      padding: const EdgeInsets.symmetric(
        horizontal: ClaySpace.lg,
        vertical: ClaySpace.lg,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: ClaySpace.md),
          ...children,
        ],
      ),
    );
  }
}

class _ChoiceRow extends StatelessWidget {
  const _ChoiceRow({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    return Semantics(
      selected: selected,
      button: true,
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: ClaySpace.md),
          child: Row(
            children: [
              // A pressed dimple with a raised dot in it when selected — the same
              // material logic as everything else, rather than a Radio.
              ClaySurface(
                style: ClayDepthStyle.pressed,
                depth: ClayDepth.nested,
                radius: ClayRadius.pill,
                width: 22,
                height: 22,
                child: selected
                    ? Center(
                        child: ClaySurface(
                          radius: ClayRadius.pill,
                          width: 11,
                          height: 11,
                          color: palette.primary,
                        ),
                      )
                    : null,
              ),
              const SizedBox(width: ClaySpace.md),
              Expanded(
                child: Text(
                  label,
                  style: Theme.of(context).textTheme.bodyLarge,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ActionRow extends StatelessWidget {
  const _ActionRow({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: ClaySpace.md),
        child: Row(
          children: [
            Icon(icon, size: 19, color: palette.primaryOnSurface),
            const SizedBox(width: ClaySpace.md),
            Expanded(
              child: Text(label, style: Theme.of(context).textTheme.bodyLarge),
            ),
            Icon(
              Directionality.of(context) == TextDirection.rtl
                  ? Icons.chevron_left_rounded
                  : Icons.chevron_right_rounded,
              size: 20,
              color: palette.textMuted,
            ),
          ],
        ),
      ),
    );
  }
}

class _VersionLine extends StatelessWidget {
  const _VersionLine();

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    return FutureBuilder<PackageInfo>(
      future: PackageInfo.fromPlatform(),
      builder: (context, snapshot) {
        final info = snapshot.data;
        return Text(
          info == null
              ? ''
              : l10n.profileAppVersion('${info.version} (${info.buildNumber})'),
          style: Theme.of(context).textTheme.labelSmall,
          textAlign: TextAlign.center,
        );
      },
    );
  }
}

/// The edit-name sheet, owning its own text controller.
///
/// Stateful purely for the controller's lifecycle: a controller created by the caller and
/// disposed when the sheet's future resolves is torn down while the field is still on
/// screen animating away. Owning it here ties disposal to this widget's own unmount, which
/// is the only moment it is genuinely safe.
class _EditNameSheet extends StatefulWidget {
  const _EditNameSheet({required this.initialName});

  final String initialName;

  @override
  State<_EditNameSheet> createState() => _EditNameSheetState();
}

class _EditNameSheetState extends State<_EditNameSheet> {
  late final _controller = TextEditingController(text: widget.initialName);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _save() => Navigator.of(context).pop(_controller.text.trim());

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          l10n.profileEditName,
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: ClaySpace.lg),
        ClayTextField(
          controller: _controller,
          label: l10n.profileName,
          autofocus: true,
          textInputAction: TextInputAction.done,
          onSubmitted: (_) => _save(),
        ),
        const SizedBox(height: ClaySpace.xl),
        ClayButton(
          label: l10n.actionSave,
          expand: true,
          onPressed: _save,
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
