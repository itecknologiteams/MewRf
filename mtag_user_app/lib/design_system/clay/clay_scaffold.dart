import 'package:flutter/material.dart';
import 'package:mtag_user_app/design_system/clay/clay_ambient.dart';
import 'package:mtag_user_app/design_system/clay/clay_button.dart';
import 'package:mtag_user_app/design_system/theme/clay_theme.dart';
import 'package:mtag_user_app/design_system/tokens/clay_metrics.dart';

/// The page shell.
///
/// No Material AppBar: an AppBar is a flat plane with an elevation shadow under
/// it, and this app has no flat planes. The title is just large text at the top
/// of the scroll, with a clay back button beside it.
class ClayScaffold extends StatelessWidget {
  const ClayScaffold({
    required this.body,
    this.title,
    this.subtitle,
    this.showBack = false,
    this.onBack,
    this.trailing,
    this.bottomNav,
    this.padHorizontal = true,
    super.key,
  });

  final Widget body;
  final String? title;
  final String? subtitle;
  final bool showBack;
  final VoidCallback? onBack;
  final Widget? trailing;
  final Widget? bottomNav;

  /// Off for full-bleed scroll views that manage their own gutters (a
  /// horizontally scrolling tag rail has to reach the screen edge).
  final bool padHorizontal;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    final textTheme = Theme.of(context).textTheme;

    final hasHeader = title != null || showBack || trailing != null;

    return Scaffold(
      backgroundColor: palette.base,
      // Pushed screens (Top Up, Vehicles, Trips, Fares) live on the ROOT navigator, above
      // AppShell — so they do not inherit its ambient glow and would land on dead flat
      // black with glass panels that have nothing to be translucent against. Lower
      // intensity than the dashboard: these are working screens, not the hero.
      body: ClayAmbient(
        intensity: 0.6,
        child: SafeArea(
          bottom: false,
          child: Column(
            children: [
              if (hasHeader)
                Padding(
                  padding: EdgeInsets.fromLTRB(
                    padHorizontal ? ClaySpace.gutter : ClaySpace.gutter,
                    ClaySpace.lg,
                    padHorizontal ? ClaySpace.gutter : ClaySpace.gutter,
                    ClaySpace.lg,
                  ),
                  child: Row(
                    children: [
                      if (showBack) ...[
                        ClayIconButton(
                          icon: Directionality.of(context) == TextDirection.rtl
                              ? Icons.arrow_forward_rounded
                              : Icons.arrow_back_rounded,
                          semanticLabel: MaterialLocalizations.of(
                            context,
                          ).backButtonTooltip,
                          onPressed:
                              onBack ?? () => Navigator.of(context).maybePop(),
                        ),
                        const SizedBox(width: ClaySpace.lg),
                      ],
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (title != null)
                              Text(
                                title!,
                                style: textTheme.headlineMedium,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            if (subtitle != null) ...[
                              const SizedBox(height: ClaySpace.xs),
                              Text(
                                subtitle!,
                                style: textTheme.bodySmall,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ],
                        ),
                      ),
                      if (trailing != null) ...[
                        const SizedBox(width: ClaySpace.md),
                        trailing!,
                      ],
                    ],
                  ),
                ),
              Expanded(
                child: padHorizontal
                    ? Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: ClaySpace.gutter,
                        ),
                        child: body,
                      )
                    : body,
              ),
              ?bottomNav,
            ],
          ),
        ),
      ),
    );
  }
}
