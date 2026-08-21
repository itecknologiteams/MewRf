import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/features/auth/presentation/session_controller.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Shown when an operator or admin signs in.
///
/// These credentials authenticate perfectly well — the role only changes what the
/// server will return. An operator on the dashboard would get an empty vehicle list
/// (they own no vehicles) and a Rs. 0 total, which looks like data loss rather than a
/// wrong app.
///
/// Two things this deliberately does not do: refuse the login (the credentials ARE
/// valid, and silently rejecting them looks broken), and expose any operator feature.
/// The app is a consumer wallet and holds no operator surface at all.
class StaffAccountNotice extends ConsumerWidget {
  const StaffAccountNotice({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final user = ref.watch(currentUserProvider);

    return Scaffold(
      backgroundColor: palette.base,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(ClaySpace.gutter),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ClayBanner(
                  icon: Icons.badge_outlined,
                  title: l10n.staffAccountTitle,
                  message: l10n.staffAccountBody(
                    user?.fullName ?? '',
                    user?.role.value ?? '',
                  ),
                ),
                const SizedBox(height: ClaySpace.xl),
                ClayButton(
                  label: l10n.staffAccountSignOut,
                  icon: Icons.logout_rounded,
                  variant: ClayButtonVariant.primary,
                  expand: true,
                  onPressed: () =>
                      ref.read(sessionControllerProvider.notifier).signOut(),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
