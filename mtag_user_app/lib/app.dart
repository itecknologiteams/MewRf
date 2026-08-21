import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mtag_user_app/core/router/app_router.dart';
import 'package:mtag_user_app/core/settings/app_settings.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

class MTagApp extends ConsumerWidget {
  const MTagApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(appSettingsProvider);
    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      title: 'M-Tag',
      debugShowCheckedModeBanner: false,
      routerConfig: router,

      // Both themes are first-class, following the system by default with a manual
      // override in Profile.
      theme: clayLightTheme(),
      darkTheme: clayDarkTheme(),
      themeMode: settings.themeMode,

      locale: settings.locale,
      localizationsDelegates: AppL10n.localizationsDelegates,
      supportedLocales: AppL10n.supportedLocales,

      builder: (context, child) {
        // Text scale is honoured but capped. This app's hero element is a 40sp
        // balance inside a fixed-height clay card; at the 2.0x some Android
        // accessibility settings allow, that figure overflows its own card and the
        // low-balance warning beside it disappears — which is worse for the user the
        // setting is meant to help. 1.4x keeps every layout intact.
        final media = MediaQuery.of(context);
        return MediaQuery(
          data: media.copyWith(
            textScaler: media.textScaler.clamp(maxScaleFactor: 1.4),
          ),
          child: child ?? const SizedBox.shrink(),
        );
      },
    );
  }
}
