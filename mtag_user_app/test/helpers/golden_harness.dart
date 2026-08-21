import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mtag_user_app/design_system/clay.dart';
import 'package:mtag_user_app/l10n/generated/app_localizations.dart';

/// Loads the bundled fonts into the test binary.
///
/// Without this every glyph in a golden is an Ahem box, which makes the images
/// useless for the thing they exist to catch: whether a balance figure at 40sp
/// actually fits, whether a status pill wraps, whether Urdu renders at all. Call
/// it once from a `setUpAll`.
Future<void> loadClayFonts() async {
  TestWidgetsFlutterBinding.ensureInitialized();

  Future<void> load(String family, List<String> paths) async {
    final loader = FontLoader(family);
    for (final path in paths) {
      final bytes = await File(path).readAsBytes();
      loader.addFont(Future.value(ByteData.sublistView(bytes)));
    }
    await loader.load();
  }

  await load('Nunito', [
    'assets/fonts/Nunito-Regular.ttf',
    'assets/fonts/Nunito-SemiBold.ttf',
    'assets/fonts/Nunito-Bold.ttf',
  ]);
  // Loaded for the same reason as the others: without it the TID and tag serials render
  // as tofu boxes in every golden, so the goldens cannot verify the one layout where
  // character-level legibility is the whole point.
  await load('Mono', [
    'assets/fonts/JetBrainsMono-Regular.ttf',
    'assets/fonts/JetBrainsMono-Bold.ttf',
  ]);
  await load('NotoSansArabic', [
    'assets/fonts/NotoSansArabic-Regular.ttf',
    'assets/fonts/NotoSansArabic-SemiBold.ttf',
    'assets/fonts/NotoSansArabic-Bold.ttf',
  ]);

  // Icons carry meaning alongside every status colour in this design system, so
  // a golden full of tofu squares cannot verify that a pill with an icon still
  // fits, or that a nav label is not being pushed out. The font ships with the
  // SDK rather than the app, hence the cache lookup; if the layout ever changes
  // the goldens fall back to boxes rather than failing the suite.
  final materialIcons = _findMaterialIconsFont();
  if (materialIcons != null) {
    await load('MaterialIcons', [materialIcons]);
  }
}

String? _findMaterialIconsFont() {
  final flutterRoot = _flutterRoot();
  if (flutterRoot == null) return null;
  final path =
      '$flutterRoot/bin/cache/artifacts/material_fonts/'
      'MaterialIcons-Regular.otf';
  return File(path).existsSync() ? path : null;
}

String? _flutterRoot() {
  final env = Platform.environment['FLUTTER_ROOT'];
  if (env != null && env.isNotEmpty) return env;
  // Under `flutter test` the resolved Dart executable lives at
  // <root>/bin/cache/dart-sdk/bin/dart.
  final parts = Platform.resolvedExecutable.split('/bin/cache/dart-sdk/');
  return parts.length > 1 ? parts.first : null;
}

/// Runs one golden in both themes.
///
/// Two files per case, `<name>_light.png` and `<name>_dark.png`, because both
/// themes are first-class here and a palette change that only breaks dark mode is
/// exactly the regression that ships.
void goldenTestBothThemes(
  String description, {
  required String fileName,
  required WidgetBuilder builder,
  Size size = const Size(420, 900),
  bool reduceMotion = false,
  TextDirection textDirection = TextDirection.ltr,
}) {
  for (final (suffix, theme) in [
    ('light', clayLightTheme()),
    ('dark', clayDarkTheme()),
  ]) {
    testWidgets('$description ($suffix)', (tester) async {
      await pumpGolden(
        tester,
        theme: theme,
        builder: builder,
        size: size,
        reduceMotion: reduceMotion,
        textDirection: textDirection,
      );
      await expectLater(
        find.byType(_GoldenHost),
        matchesGoldenFile('goldens/${fileName}_$suffix.png'),
      );
    });
  }
}

Future<void> pumpGolden(
  WidgetTester tester, {
  required ThemeData theme,
  required WidgetBuilder builder,
  Size size = const Size(420, 900),
  bool reduceMotion = false,
  TextDirection textDirection = TextDirection.ltr,
  Locale locale = const Locale('en'),
}) async {
  tester.view
    ..physicalSize = size
    ..devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(
    MediaQuery(
      data: MediaQueryData(
        size: size,
        disableAnimations: reduceMotion,
      ),
      child: Directionality(
        textDirection: textDirection,
        child: MaterialApp(
          debugShowCheckedModeBanner: false,
          theme: theme,
          // Localisation delegates, so a golden can render a REAL widget rather than a
          // hand-built replica of one. Without these, any widget calling AppL10n.of throws
          // a null-check the moment it is golden-tested — which is what happened the first
          // time this harness was pointed at an actual feature widget.
          localizationsDelegates: AppL10n.localizationsDelegates,
          supportedLocales: AppL10n.supportedLocales,
          locale: locale,
          home: _GoldenHost(builder: builder),
        ),
      ),
    ),
  );
  // Let the shimmer controller settle into a fixed frame. pumpAndSettle would
  // hang on a repeating animation, so the frames are advanced explicitly.
  await tester.pump(const Duration(milliseconds: 16));
}

class _GoldenHost extends StatelessWidget {
  const _GoldenHost({required this.builder});

  final WidgetBuilder builder;

  @override
  Widget build(BuildContext context) {
    final palette = ClayTheme.of(context).palette;
    return Scaffold(
      backgroundColor: palette.base,
      body: Padding(
        padding: const EdgeInsets.all(ClaySpace.xl),
        child: builder(context),
      ),
    );
  }
}
