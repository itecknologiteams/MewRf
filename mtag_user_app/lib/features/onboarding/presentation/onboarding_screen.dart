import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mtag_user_app/core/router/app_router.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// The first screen a new install shows.
///
/// Three panels explaining what an M-Tag does, then the two things a user can actually do:
/// set up a password for the account a booth already made them, or sign in if they have one.
///
/// The help icon exists because those two options are not self-explanatory — "set up my
/// account" sounds like signup, and this system has no signup. The sheet says so plainly and
/// tells someone with no tag where to go.
class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final _pages = PageController();
  int _index = 0;

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  void _showHelp() {
    final l10n = AppL10n.of(context);
    showClaySheet<void>(
      context: context,
      builder: (sheetContext) => Padding(
        padding: const EdgeInsets.all(ClaySpace.gutter),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              l10n.helpTitle,
              style: Theme.of(sheetContext).textTheme.titleLarge,
            ),
            const SizedBox(height: ClaySpace.md),
            Text(
              l10n.helpBody,
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
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppL10n.of(context);
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;

    final panels = [
      (Icons.sensors_rounded, l10n.onboardingTitle1, l10n.onboardingBody1),
      (
        Icons.account_balance_wallet_rounded,
        l10n.onboardingTitle2,
        l10n.onboardingBody2,
      ),
      (Icons.add_card_rounded, l10n.onboardingTitle3, l10n.onboardingBody3),
    ];
    final isLast = _index == panels.length - 1;

    return Scaffold(
      backgroundColor: palette.base,
      body: ClayAmbient(
        child: SafeArea(
          child: Column(
            children: [
              // Help sits top-right, reachable before the user has committed to anything.
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: ClaySpace.md),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    ClayIconButton(
                      icon: Icons.help_outline_rounded,
                      semanticLabel: l10n.helpTitle,
                      onPressed: _showHelp,
                    ),
                  ],
                ),
              ),

              Expanded(
                child: PageView.builder(
                  controller: _pages,
                  itemCount: panels.length,
                  onPageChanged: (i) => setState(() => _index = i),
                  itemBuilder: (context, i) {
                    final (icon, title, body) = panels[i];
                    return Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: ClaySpace.xxl,
                      ),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          // Claymorphic medallion, not a 3D render. The design system's own
                          // clay style is dimensional enough to carry an illustration slot,
                          // and it needs no asset per panel per theme.
                          ClaySurface(
                            style: ClayDepthStyle.clay,
                            radius: ClayRadius.hero + 12,
                            depth: ClayDepth.hero,
                            width: 148,
                            height: 148,
                            child: Center(
                              child: Icon(
                                icon,
                                size: 62,
                                color: palette.primary,
                              ),
                            ),
                          ),
                          const SizedBox(height: ClaySpace.xxl),
                          Text(
                            title,
                            style: textTheme.headlineMedium,
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: ClaySpace.md),
                          Text(
                            body,
                            style: textTheme.bodyMedium?.copyWith(
                              color: palette.textMuted,
                            ),
                            textAlign: TextAlign.center,
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),

              // Page dots.
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  for (var i = 0; i < panels.length; i++)
                    AnimatedContainer(
                      duration: clayDuration(context, ClayMotion.press),
                      curve: ClayMotion.ease,
                      margin: const EdgeInsets.symmetric(horizontal: 4),
                      width: i == _index ? 22 : 7,
                      height: 7,
                      decoration: BoxDecoration(
                        color: i == _index ? palette.primary : palette.border,
                        borderRadius: BorderRadius.circular(ClayRadius.pill),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: ClaySpace.xl),

              Padding(
                padding: const EdgeInsets.fromLTRB(
                  ClaySpace.gutter,
                  0,
                  ClaySpace.gutter,
                  ClaySpace.lg,
                ),
                child: Column(
                  children: [
                    ClayButton(
                      label: isLast
                          ? l10n.onboardingGetStarted
                          : l10n.onboardingNext,
                      variant: ClayButtonVariant.primary,
                      expand: true,
                      onPressed: isLast
                          ? () => context.push(Routes.phoneEntry)
                          : () => _pages.nextPage(
                              duration: ClayMotion.page,
                              curve: ClayMotion.ease,
                            ),
                    ),
                    const SizedBox(height: ClaySpace.md),
                    ClayButton(
                      label: l10n.onboardingHaveAccount,
                      variant: ClayButtonVariant.ghost,
                      expand: true,
                      onPressed: () => context.push(Routes.login),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
