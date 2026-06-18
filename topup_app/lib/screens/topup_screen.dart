import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../main.dart' show kInk, kMuted, kBorder, kSurface, kBg;
import '../models.dart';
import '../services/api_service.dart';
import '../services/rfid_service.dart';
import 'login_screen.dart';
import 'server_config_screen.dart';

class TopupScreen extends StatefulWidget {
  const TopupScreen({super.key});

  @override
  State<TopupScreen> createState() => _TopupScreenState();
}

class _TopupScreenState extends State<TopupScreen> {
  final _tidCtl = TextEditingController();
  final _nameCtl = TextEditingController();
  final _cnicCtl = TextEditingController();
  final _phoneCtl = TextEditingController();
  final _plateCtl = TextEditingController();
  final _amountCtl = TextEditingController();

  String _epc = '';
  bool _verified = false;
  bool _found = false;
  String _balance = '0';

  bool _connected = false;
  bool _scanning = false;
  bool _busy = false;
  String? _status;
  bool _statusError = false;
  StreamSubscription<TagRead>? _sub;

  @override
  void initState() {
    super.initState();
    _initReader();
  }

  Future<void> _initReader() async {
    final ok = await RfidService.instance.connect();
    _sub = RfidService.instance.tagStream.listen(_onTag);
    if (mounted) setState(() => _connected = ok);
  }

  void _onTag(TagRead t) {
    if (!_scanning || t.tid.isEmpty) return;
    RfidService.instance.stopInventory();
    setState(() {
      _scanning = false;
      _tidCtl.text = t.tid;
      _epc = t.epc;
    });
    _verify();
  }

  Future<void> _scan() async {
    if (!_connected) {
      final ok = await RfidService.instance.connect();
      setState(() => _connected = ok);
      if (!ok) {
        _setStatus('Reader unavailable — type the TID manually.', true);
        return;
      }
    }
    setState(() => _scanning = true);
    await RfidService.instance.startInventory();
  }

  void _setStatus(String msg, bool err) => setState(() {
        _status = msg;
        _statusError = err;
      });

  Future<void> _verify() async {
    final tid = _tidCtl.text.replaceAll(' ', '').toUpperCase().trim();
    if (tid.isEmpty) {
      _setStatus('Enter or scan a TID first.', true);
      return;
    }
    setState(() {
      _busy = true;
      _status = null;
    });
    try {
      final d = await ApiService.instance.topupLookup(tid);
      setState(() {
        _verified = true;
        _found = d['found'] == true;
        _epc = (d['epc']?.toString().isNotEmpty ?? false) ? d['epc'].toString() : _epc;
        if (_found) {
          _nameCtl.text = d['consumer_name']?.toString() ?? '';
          _cnicCtl.text = _formatCnic(d['cnic']?.toString() ?? '');
          _phoneCtl.text = d['phone']?.toString() ?? '';
          _plateCtl.text = d['plate']?.toString() ?? '';
          _balance = d['balance']?.toString() ?? '0';
        } else {
          _nameCtl.clear();
          _cnicCtl.clear();
          _phoneCtl.clear();
          _plateCtl.clear();
          _balance = '0';
        }
      });
    } catch (e) {
      _setStatus(e.toString().replaceFirst('Exception: ', ''), true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _reset() {
    _tidCtl.clear();
    _nameCtl.clear();
    _cnicCtl.clear();
    _phoneCtl.clear();
    _plateCtl.clear();
    _amountCtl.clear();
    _epc = '';
    _verified = false;
    _found = false;
    _balance = '0';
  }

  Future<void> _submit() async {
    final amt = _amountCtl.text.trim();
    if (amt.isEmpty || (double.tryParse(amt) ?? 0) <= 0) {
      _setStatus('Enter a valid amount.', true);
      return;
    }
    if (!_found &&
        (_nameCtl.text.trim().isEmpty || _phoneCtl.text.trim().isEmpty || _plateCtl.text.trim().isEmpty)) {
      _setStatus('Name, phone and vehicle registration are required to register.', true);
      return;
    }
    setState(() {
      _busy = true;
      _status = null;
    });
    try {
      final d = await ApiService.instance.cashTopup(
        tid: _tidCtl.text.replaceAll(' ', '').toUpperCase().trim(),
        amount: amt,
        epc: _epc,
        consumerName: _nameCtl.text.trim(),
        cnic: _cnicCtl.text.replaceAll(RegExp(r'\D'), ''),
        phone: _phoneCtl.text.trim(),
        vehicleReg: _plateCtl.text.trim(),
      );
      final reg = d['registered'] == true;
      setState(() {
        _reset();
        _statusError = false;
        _status = '${reg ? 'Registered & topped up' : 'Topup successful'} — new balance Rs ${d['new_balance']}';
      });
    } catch (e) {
      _setStatus(e.toString().replaceFirst('Exception: ', ''), true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _logout() async {
    await RfidService.instance.disconnect();
    await ApiService.instance.logout();
    if (!mounted) return;
    Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => const LoginScreen()));
  }

  @override
  void dispose() {
    _sub?.cancel();
    RfidService.instance.disconnect();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isAdmin = ApiService.instance.isAdmin;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Cash Topup'),
        shape: const Border(bottom: BorderSide(color: kBorder)),
        actions: [
          if (isAdmin)
            IconButton(
              icon: const Icon(Icons.tune, size: 21),
              tooltip: 'Server settings',
              onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ServerConfigScreen())),
            ),
          IconButton(icon: const Icon(Icons.logout, size: 20), tooltip: 'Logout', onPressed: _logout),
          const SizedBox(width: 4),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _tagCard(),
          if (_verified) ...[
            const SizedBox(height: 14),
            _detailsCard(),
          ],
          if (_status != null) ...[
            const SizedBox(height: 14),
            _statusBanner(),
          ],
        ],
      ),
    );
  }

  Widget _tagCard() {
    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('Tag', style: TextStyle(fontWeight: FontWeight.w700, color: kInk)),
              const Spacer(),
              _StatusDot(connected: _connected, scanning: _scanning),
            ],
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _tidCtl,
            decoration: const InputDecoration(hintText: 'Scan or enter TID'),
            style: const TextStyle(fontFamily: 'monospace'),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _scanning ? null : _scan,
                  icon: Icon(_scanning ? Icons.sensors : Icons.nfc, size: 18),
                  label: Text(_scanning ? 'Scanning…' : 'Scan'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: FilledButton(
                  onPressed: _busy ? null : _verify,
                  child: _busy && !_verified
                      ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : const Text('Verify'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _detailsCard() {
    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(_found ? 'Registered consumer' : 'New consumer',
                  style: const TextStyle(fontWeight: FontWeight.w700, color: kInk)),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: _found ? const Color(0xFFECFDF5) : const Color(0xFFFFF7ED),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(_found ? 'Existing' : 'Register',
                    style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: _found ? const Color(0xFF047857) : const Color(0xFFC2410C))),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _ro('TID', _tidCtl.text),
          if (_epc.isNotEmpty) _ro('EPC', _epc),
          if (_found) _ro('Current balance', 'Rs $_balance'),
          const SizedBox(height: 6),
          _field('Consumer name', _nameCtl, readOnly: _found),
          _field('CNIC', _cnicCtl,
              readOnly: _found, keyboard: TextInputType.number, formatters: [CnicInputFormatter()]),
          _field('Phone', _phoneCtl, readOnly: _found, keyboard: TextInputType.phone),
          _field('Vehicle registration', _plateCtl, readOnly: _found),
          _field('Amount (Rs)', _amountCtl, keyboard: const TextInputType.numberWithOptions(decimal: true)),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: _busy ? null : _submit,
              icon: _busy
                  ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.payments_outlined, size: 18),
              label: Text(_found ? 'Top up (Cash)' : 'Register & Top up'),
            ),
          ),
        ],
      ),
    );
  }

  // ── small helpers ─────────────────────────────────────────────────────────
  Widget _card({required Widget child}) => Container(
        decoration: BoxDecoration(
          color: kSurface,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: kBorder),
        ),
        padding: const EdgeInsets.all(16),
        child: child,
      );

  Widget _ro(String label, String value) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(width: 120, child: Text(label, style: const TextStyle(fontSize: 12.5, color: kMuted))),
            Expanded(
              child: Text(value.isEmpty ? '—' : value,
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: kInk, fontFamily: 'monospace')),
            ),
          ],
        ),
      );

  Widget _field(String label, TextEditingController c,
          {bool readOnly = false, TextInputType? keyboard, List<TextInputFormatter>? formatters}) =>
      Padding(
        padding: const EdgeInsets.only(top: 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: kInk)),
            const SizedBox(height: 6),
            TextField(
              controller: c,
              readOnly: readOnly,
              keyboardType: keyboard,
              inputFormatters: formatters,
              decoration: InputDecoration(
                isDense: true,
                fillColor: readOnly ? kBg : kSurface,
              ),
            ),
          ],
        ),
      );

  Widget _statusBanner() => Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
        decoration: BoxDecoration(
          color: _statusError ? const Color(0xFFFEF2F2) : const Color(0xFFECFDF5),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Row(
          children: [
            Icon(_statusError ? Icons.warning_amber_rounded : Icons.check_circle_outline,
                size: 18, color: _statusError ? const Color(0xFFB91C1C) : const Color(0xFF047857)),
            const SizedBox(width: 8),
            Expanded(
              child: Text(_status!,
                  style: TextStyle(fontSize: 13, color: _statusError ? const Color(0xFFB91C1C) : const Color(0xFF047857))),
            ),
          ],
        ),
      );
}

/// Format 13 raw digits as a Pakistani CNIC: XXXXX-XXXXXXX-X.
String _formatCnic(String raw) {
  final d = raw.replaceAll(RegExp(r'\D'), '');
  if (d.length != 13) return raw;
  return '${d.substring(0, 5)}-${d.substring(5, 12)}-${d.substring(12)}';
}

/// Auto-inserts CNIC dashes (5-7-1) while typing.
class CnicInputFormatter extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(TextEditingValue oldValue, TextEditingValue newValue) {
    var d = newValue.text.replaceAll(RegExp(r'\D'), '');
    if (d.length > 13) d = d.substring(0, 13);
    final b = StringBuffer();
    for (var i = 0; i < d.length; i++) {
      b.write(d[i]);
      if ((i == 4 || i == 11) && i != d.length - 1) b.write('-');
    }
    final t = b.toString();
    return TextEditingValue(text: t, selection: TextSelection.collapsed(offset: t.length));
  }
}

class _StatusDot extends StatelessWidget {
  final bool connected;
  final bool scanning;
  const _StatusDot({required this.connected, required this.scanning});

  @override
  Widget build(BuildContext context) {
    final color = scanning
        ? const Color(0xFF2563EB)
        : connected
            ? const Color(0xFF10B981)
            : const Color(0xFFF59E0B);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 6),
        Text(scanning ? 'Scanning…' : connected ? 'Reader ready' : 'Manual',
            style: const TextStyle(fontSize: 11.5, color: kMuted)),
      ],
    );
  }
}
