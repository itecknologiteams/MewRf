import 'package:flutter/material.dart';

import '../main.dart' show kInk, kMuted, kSurface;
import '../services/api_service.dart';
import '../services/settings_service.dart';
import 'scan_screen.dart';
import 'server_config_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _phone = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  bool _obscure = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    SettingsService.getLastPhone().then((p) {
      if (mounted) setState(() => _phone.text = p);
    });
  }

  Future<void> _login() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ApiService.instance.login(_phone.text.trim(), _password.text);
      await SettingsService.setLastPhone(_phone.text.trim());
      if (!mounted) return;
      Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => const ScanScreen()));
    } catch (e) {
      setState(() => _error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kSurface,
      body: SafeArea(
        child: Stack(
          children: [
            // Server settings (setup) — top-right, discreet.
            Align(
              alignment: Alignment.topRight,
              child: IconButton(
                icon: const Icon(Icons.tune, size: 20, color: kMuted),
                tooltip: 'Server settings',
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const ServerConfigScreen()),
                ),
              ),
            ),
            Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 40),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 380),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Logo
                  Center(
                    child: Image.asset(
                      'assets/logo.png',
                      height: 76,
                      fit: BoxFit.contain,
                      errorBuilder: (_, __, ___) => Container(
                        width: 60,
                        height: 60,
                        decoration: BoxDecoration(color: kInk, borderRadius: BorderRadius.circular(16)),
                        child: const Icon(Icons.nfc, color: Colors.white, size: 30),
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  const Text('Q-Tag Scanner',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: kInk, letterSpacing: -0.4)),
                  const SizedBox(height: 6),
                  const Text('Sign in to continue',
                      textAlign: TextAlign.center, style: TextStyle(fontSize: 13.5, color: kMuted)),
                  const SizedBox(height: 36),

                  _label('Phone'),
                  const SizedBox(height: 7),
                  TextField(
                    controller: _phone,
                    keyboardType: TextInputType.phone,
                    decoration: const InputDecoration(hintText: '03001234567'),
                  ),
                  const SizedBox(height: 18),

                  _label('Password'),
                  const SizedBox(height: 7),
                  TextField(
                    controller: _password,
                    obscureText: _obscure,
                    onSubmitted: (_) => _login(),
                    decoration: InputDecoration(
                      hintText: '••••••••',
                      suffixIcon: IconButton(
                        icon: Icon(_obscure ? Icons.visibility_off_outlined : Icons.visibility_outlined,
                            size: 20, color: kMuted),
                        onPressed: () => setState(() => _obscure = !_obscure),
                      ),
                    ),
                  ),

                  // Error
                  AnimatedSize(
                    duration: const Duration(milliseconds: 180),
                    child: _error == null
                        ? const SizedBox(width: double.infinity)
                        : Padding(
                            padding: const EdgeInsets.only(top: 16),
                            child: Row(
                              children: [
                                const Icon(Icons.error_outline, color: Color(0xFFB91C1C), size: 17),
                                const SizedBox(width: 8),
                                Expanded(child: Text(_error!, style: const TextStyle(color: Color(0xFFB91C1C), fontSize: 13))),
                              ],
                            ),
                          ),
                  ),

                  const SizedBox(height: 28),
                  FilledButton(
                    onPressed: _busy ? null : _login,
                    child: _busy
                        ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : const Text('Sign in'),
                  ),
                ],
              ),
            ),
          ),
        ),
          ],
        ),
      ),
    );
  }

  Widget _label(String text) => Text(
        text,
        style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: kInk, letterSpacing: 0.1),
      );
}
