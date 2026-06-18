import 'dart:async';
import 'package:flutter/material.dart';

import '../main.dart' show kInk, kMuted, kBorder, kSurface, kBg;
import '../models.dart';
import '../services/api_service.dart';
import '../services/rfid_service.dart';
import 'login_screen.dart';
import 'server_config_screen.dart';

class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  final Map<String, TagRead> _tags = {};
  final _tidCtl = TextEditingController();
  final _epcCtl = TextEditingController();

  bool _connected = false;
  bool _scanning = false;
  bool _busy = false;
  final Set<String> _dupTids = {};
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
    _sub = RfidService.instance.tagStream.listen(_addTag);
    if (mounted) setState(() => _connected = ok);
  }

  void _addTag(TagRead tag) {
    if (tag.tid.isEmpty) return;
    setState(() => _tags[tag.tid] = tag);
  }

  void _manualAdd() {
    final tid = _tidCtl.text.replaceAll(' ', '').toUpperCase().trim();
    final epc = _epcCtl.text.trim();
    if (tid.isEmpty) return;
    _addTag(TagRead(tid: tid, epc: epc));
    _tidCtl.clear();
    _epcCtl.clear();
  }

  void _remove(String tid) => setState(() {
        _tags.remove(tid);
        _dupTids.remove(tid);
      });

  Future<void> _toggleScan() async {
    if (_scanning) {
      await RfidService.instance.stopInventory();
      setState(() => _scanning = false);
    } else {
      await RfidService.instance.startInventory();
      setState(() => _scanning = true);
    }
  }

  Future<void> _insert() async {
    if (_tags.isEmpty) {
      setState(() {
        _status = 'No tags to insert.';
        _statusError = true;
      });
      return;
    }
    setState(() {
      _busy = true;
      _status = null;
    });
    try {
      final list = _tags.values.toList();
      final existing = await ApiService.instance.checkExisting(list.map((t) => t.tid).toList());
      if (existing.isNotEmpty) {
        final dup = existing.toSet();
        final where = <String>[];
        for (var i = 0; i < list.length; i++) {
          if (dup.contains(list[i].tid)) where.add('#${i + 1}');
        }
        setState(() {
          _dupTids
            ..clear()
            ..addAll(dup);
          _statusError = true;
          _status = '${dup.length} already Uploaded — remove ${where.join(', ')} (red), then Insert again.';
        });
        return;
      }
      _dupTids.clear();
      final res = await ApiService.instance.bulkInsert(list);
      setState(() {
        _statusError = false;
        _status = 'Inserted ${res['added']} tag(s) into the database.';
        _tags.clear();
      });
    } catch (e) {
      setState(() {
        _statusError = true;
        _status = e.toString().replaceFirst('Exception: ', '');
      });
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
    final tags = _tags.values.toList();
    final isAdmin = ApiService.instance.isAdmin;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan Tags'),
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
      body: Column(
        children: [
          _header(tags.length),
          _manualRow(),
          Expanded(child: tags.isEmpty ? _empty() : _list(tags)),
          _statusBar(),
          _bottomBar(tags.length),
        ],
      ),
    );
  }

  // ── Header: status • animated count • start/stop ──────────────────────────
  Widget _header(int count) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 18),
      decoration: const BoxDecoration(
        color: kSurface,
        border: Border(bottom: BorderSide(color: kBorder)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _Dot(active: _connected, scanning: _scanning),
              const SizedBox(width: 7),
              Text(
                !_connected
                    ? 'Reader unavailable'
                    : _scanning
                        ? 'Scanning…'
                        : 'Reader connected',
                style: const TextStyle(fontSize: 12.5, color: kMuted, fontWeight: FontWeight.w500),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    AnimatedSwitcher(
                      duration: const Duration(milliseconds: 220),
                      transitionBuilder: (c, a) => ScaleTransition(scale: a, child: FadeTransition(opacity: a, child: c)),
                      child: Text('$count',
                          key: ValueKey(count),
                          style: const TextStyle(fontSize: 44, fontWeight: FontWeight.w700, color: kInk, height: 1, letterSpacing: -1)),
                    ),
                    const SizedBox(width: 8),
                    const Padding(
                      padding: EdgeInsets.only(bottom: 4),
                      child: Text('tags', style: TextStyle(fontSize: 13, color: kMuted)),
                    ),
                  ],
                ),
              ),
              _scanning
                  ? OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(
                        foregroundColor: const Color(0xFFB91C1C),
                        side: const BorderSide(color: Color(0xFFFCA5A5)),
                      ),
                      onPressed: _toggleScan,
                      icon: const Icon(Icons.stop, size: 18),
                      label: const Text('Stop'),
                    )
                  : FilledButton.icon(
                      onPressed: _connected ? _toggleScan : null,
                      icon: const Icon(Icons.play_arrow, size: 18),
                      label: const Text('Start'),
                    ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _manualRow() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 6),
      child: Row(
        children: [
          Expanded(flex: 3, child: TextField(controller: _tidCtl, decoration: const InputDecoration(hintText: 'Enter TID', isDense: true))),
          const SizedBox(width: 8),
          Expanded(flex: 2, child: TextField(controller: _epcCtl, decoration: const InputDecoration(hintText: 'EPC', isDense: true))),
          const SizedBox(width: 6),
          SizedBox(
            height: 48,
            width: 48,
            child: FilledButton(
              style: FilledButton.styleFrom(padding: EdgeInsets.zero, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
              onPressed: _manualAdd,
              child: const Icon(Icons.add, size: 22),
            ),
          ),
        ],
      ),
    );
  }

  Widget _empty() => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.nfc_outlined, size: 44, color: Colors.grey.shade300),
            const SizedBox(height: 10),
            Text('No tags yet', style: TextStyle(color: Colors.grey.shade400, fontSize: 13.5)),
            const SizedBox(height: 2),
            Text('Scan or add a tag to begin', style: TextStyle(color: Colors.grey.shade400, fontSize: 12)),
          ],
        ),
      );

  Widget _list(List<TagRead> tags) {
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      itemCount: tags.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (_, i) {
        final t = tags[i];
        final isDup = _dupTids.contains(t.tid);
        return Dismissible(
          key: ValueKey(t.tid),
          direction: DismissDirection.endToStart,
          onDismissed: (_) => _remove(t.tid),
          background: Container(
            alignment: Alignment.centerRight,
            padding: const EdgeInsets.only(right: 18),
            decoration: BoxDecoration(color: const Color(0xFFFEE2E2), borderRadius: BorderRadius.circular(12)),
            child: const Icon(Icons.delete_outline, color: Color(0xFFB91C1C)),
          ),
          child: Container(
            decoration: BoxDecoration(
              color: isDup ? const Color(0xFFFEF2F2) : kSurface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: isDup ? const Color(0xFFFCA5A5) : kBorder),
            ),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            child: Row(
              children: [
                Container(
                  width: 26,
                  height: 26,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: isDup ? const Color(0xFFFECACA) : kBg,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text('${i + 1}',
                      style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: isDup ? const Color(0xFFB91C1C) : kMuted)),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(t.tid, style: const TextStyle(fontFamily: 'monospace', fontWeight: FontWeight.w600, fontSize: 13, color: kInk)),
                      const SizedBox(height: 2),
                      Text(
                        isDup ? 'Already Uploaded' : 'EPC  ${t.epc.isEmpty ? '—' : t.epc}',
                        style: TextStyle(
                          fontFamily: isDup ? null : 'monospace',
                          fontSize: 11,
                          color: isDup ? const Color(0xFFB91C1C) : kMuted,
                          fontWeight: isDup ? FontWeight.w600 : FontWeight.normal,
                        ),
                      ),
                    ],
                  ),
                ),
                InkWell(
                  borderRadius: BorderRadius.circular(20),
                  onTap: () => _remove(t.tid),
                  child: Padding(
                    padding: const EdgeInsets.all(4),
                    child: Icon(Icons.close, size: 17, color: isDup ? const Color(0xFFB91C1C) : kMuted),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _statusBar() {
    return AnimatedSize(
      duration: const Duration(milliseconds: 180),
      child: _status == null
          ? const SizedBox(width: double.infinity)
          : Container(
              width: double.infinity,
              margin: const EdgeInsets.fromLTRB(16, 0, 16, 4),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: _statusError ? const Color(0xFFFEF2F2) : const Color(0xFFECFDF5),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                children: [
                  Icon(_statusError ? Icons.warning_amber_rounded : Icons.check_circle_outline,
                      size: 17, color: _statusError ? const Color(0xFFB91C1C) : const Color(0xFF047857)),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(_status!,
                        style: TextStyle(fontSize: 12.5, color: _statusError ? const Color(0xFFB91C1C) : const Color(0xFF047857))),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _bottomBar(int count) {
    return Container(
      decoration: const BoxDecoration(
        color: kSurface,
        border: Border(top: BorderSide(color: kBorder)),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              OutlinedButton(
                onPressed: _tags.isEmpty
                    ? null
                    : () => setState(() {
                          _tags.clear();
                          _dupTids.clear();
                          _status = null;
                        }),
                child: const Text('Clear'),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: FilledButton(
                  onPressed: _busy || _tags.isEmpty ? null : _insert,
                  child: _busy
                      ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : Text(count == 0 ? 'Upload' : 'Upload $count tag${count == 1 ? '' : 's'}'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Status dot — grey (off), green (connected), pulsing green (scanning).
class _Dot extends StatefulWidget {
  final bool active;
  final bool scanning;
  const _Dot({required this.active, required this.scanning});

  @override
  State<_Dot> createState() => _DotState();
}

class _DotState extends State<_Dot> with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 900))..repeat(reverse: true);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final color = !widget.active
        ? const Color(0xFFF59E0B)
        : const Color(0xFF10B981);
    final dot = Container(width: 9, height: 9, decoration: BoxDecoration(color: color, shape: BoxShape.circle));
    if (!widget.scanning) return dot;
    return FadeTransition(opacity: Tween(begin: 0.35, end: 1.0).animate(_c), child: dot);
  }
}
