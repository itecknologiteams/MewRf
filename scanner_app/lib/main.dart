import 'package:flutter/material.dart';

import 'services/api_service.dart';
import 'screens/login_screen.dart';
import 'screens/scan_screen.dart';

void main() => runApp(const MtagScannerApp());

// ── Sober, minimal palette ────────────────────────────────────────────────
const kInk = Color(0xFF111827); // primary (charcoal) — buttons, headings
const kBg = Color(0xFFF7F8FA); // app background
const kSurface = Color(0xFFFFFFFF);
const kBorder = Color(0xFFE6E8EC); // hairline borders
const kMuted = Color(0xFF6B7280); // secondary text
// kept for backward-compatible imports; now an alias of the ink color
const kBrand = kInk;

class MtagScannerApp extends StatelessWidget {
  const MtagScannerApp({super.key});

  @override
  Widget build(BuildContext context) {
    final scheme = ColorScheme.fromSeed(seedColor: kInk, primary: kInk);
    return MaterialApp(
      title: 'QTag',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: scheme,
        scaffoldBackgroundColor: kBg,
        splashFactory: InkRipple.splashFactory,
        appBarTheme: const AppBarTheme(
          backgroundColor: kSurface,
          foregroundColor: kInk,
          centerTitle: false,
          elevation: 0,
          scrolledUnderElevation: 0.5,
          titleTextStyle: TextStyle(color: kInk, fontSize: 18, fontWeight: FontWeight.w600, letterSpacing: -0.2),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: kSurface,
          isDense: true,
          contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 15),
          labelStyle: const TextStyle(color: kMuted),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: kBorder)),
          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: kBorder)),
          focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: kInk, width: 1.4)),
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            backgroundColor: kInk,
            foregroundColor: Colors.white,
            disabledBackgroundColor: const Color(0xFFD1D5DB),
            elevation: 0,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            padding: const EdgeInsets.symmetric(vertical: 15),
            textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, letterSpacing: -0.1),
          ),
        ),
        outlinedButtonTheme: OutlinedButtonThemeData(
          style: OutlinedButton.styleFrom(
            foregroundColor: kInk,
            side: const BorderSide(color: kBorder),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            padding: const EdgeInsets.symmetric(vertical: 13, horizontal: 16),
          ),
        ),
      ),
      home: const _Decider(),
    );
  }
}

class _Decider extends StatelessWidget {
  const _Decider();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<bool>(
      future: ApiService.instance.isLoggedIn(),
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Scaffold(
            backgroundColor: kBg,
            body: Center(child: CircularProgressIndicator(color: kInk, strokeWidth: 2.5)),
          );
        }
        return snap.data == true ? const ScanScreen() : const LoginScreen();
      },
    );
  }
}
