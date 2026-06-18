import 'package:dio/dio.dart';
import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';

import '../models.dart';
import 'settings_service.dart';

/// Talks to the m-tag backend. Auth is cookie-based: login sets httpOnly
/// cookies which the cookie jar captures and resends on later requests (a
/// native HTTP client sees httpOnly cookies — that restriction is browser-only).
class ApiService {
  ApiService._();
  static final ApiService instance = ApiService._();

  late Dio _dio;
  final CookieJar _jar = CookieJar();
  bool _ready = false;

  // Set on login / session check — used to gate admin-only UI (server config).
  String? role;
  String? fullName;
  bool get isAdmin => role == 'admin';

  Future<void> _ensure() async {
    if (_ready) return;
    final baseUrl = await SettingsService.getBaseUrl();
    _dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 8),
      receiveTimeout: const Duration(seconds: 12),
      // Don't throw on non-2xx; we read the body ourselves.
      validateStatus: (_) => true,
      headers: {'Content-Type': 'application/json'},
    ));
    _dio.interceptors.add(CookieManager(_jar));
    _ready = true;
  }

  /// Re-read the base URL (after the user changes it on the config screen).
  Future<void> reconfigure() async {
    _ready = false;
    await _jar.deleteAll();
    await _ensure();
  }

  String _message(Response r) {
    final d = r.data;
    if (d is Map && d['message'] != null) return d['message'].toString();
    return 'HTTP ${r.statusCode}';
  }

  Future<String> login(String phone, String password) async {
    await _ensure();
    final r = await _dio.post('/auth/login/', data: {'phone': phone, 'password': password});
    if (r.statusCode == 200 && r.data is Map && r.data['success'] == true) {
      final d = r.data['data'] as Map?;
      fullName = (d?['full_name'] ?? phone).toString();
      role = d?['role']?.toString();
      return fullName!;
    }
    throw Exception(_message(r));
  }

  Future<bool> isLoggedIn() async {
    try {
      await _ensure();
      final r = await _dio.get('/auth/me/');
      if (r.statusCode == 200 && r.data is Map && r.data['success'] == true) {
        final d = r.data['data'] as Map?;
        fullName = d?['full_name']?.toString();
        role = d?['user_role']?.toString();
        return true;
      }
      return false;
    } catch (_) {
      // Backend unreachable / timeout → treat as not logged in (show Login).
      return false;
    }
  }

  Future<void> logout() async {
    await _ensure();
    try {
      await _dio.post('/auth/logout/');
    } finally {
      await _jar.deleteAll();
      role = null;
      fullName = null;
    }
  }

  /// Buffer mode: post each scan to /vehicles/tags/scan/ (web app polls it).
  Future<void> sendToBuffer(TagRead tag) async {
    await _ensure();
    final r = await _dio.post('/vehicles/tags/scan/', data: tag.toJson());
    if (!(r.statusCode == 200 && r.data is Map && r.data['success'] == true)) {
      throw Exception(_message(r));
    }
  }

  /// Returns the subset of the given TIDs that already exist in the DB.
  Future<List<String>> checkExisting(List<String> tids) async {
    await _ensure();
    final r = await _dio.post('/vehicles/tags/check/', data: {'tids': tids});
    if (r.statusCode == 200 && r.data is Map && r.data['success'] == true) {
      final ex = (r.data['data']?['existing'] as List?) ?? [];
      return ex.map((e) => e.toString()).toList();
    }
    throw Exception(_message(r));
  }

  /// Bulk-insert tags (status=deactivated, auto serial).
  /// Returns { added, skipped, errors, results }.
  Future<Map<String, dynamic>> bulkInsert(List<TagRead> tags) async {
    await _ensure();
    final r = await _dio.post('/vehicles/tags/bulk/',
        data: {'tags': tags.map((t) => t.toJson()).toList()});
    if (r.statusCode != null && r.statusCode! < 300 && r.data is Map && r.data['success'] == true) {
      return Map<String, dynamic>.from(r.data['data'] as Map);
    }
    throw Exception(_message(r));
  }

  // ── Topup ────────────────────────────────────────────────────────────────

  /// Verify a tag by TID. Returns { found, tid, epc, consumer_name, cnic,
  /// phone, plate, balance }. found=false → register on topup.
  Future<Map<String, dynamic>> topupLookup(String tid) async {
    await _ensure();
    final r = await _dio.post('/accounts/topup/lookup/', data: {'tid': tid});
    if (r.statusCode == 200 && r.data is Map && r.data['success'] == true) {
      return Map<String, dynamic>.from(r.data['data'] as Map);
    }
    throw Exception(_message(r));
  }

  /// Cash topup. Existing tag → pass {tid, amount}. New tag → also pass
  /// consumerName/cnic/phone/epc to register. Returns the result map.
  Future<Map<String, dynamic>> cashTopup({
    required String tid,
    required String amount,
    String epc = '',
    String consumerName = '',
    String cnic = '',
    String phone = '',
    String vehicleReg = '',
  }) async {
    await _ensure();
    final r = await _dio.post('/accounts/topup/cash/', data: {
      'tid': tid,
      'amount': amount,
      'epc': epc,
      'consumer_name': consumerName,
      'cnic': cnic,
      'phone': phone,
      'vehicle_reg': vehicleReg,
    });
    if (r.statusCode != null && r.statusCode! < 300 && r.data is Map && r.data['success'] == true) {
      return Map<String, dynamic>.from(r.data['data'] as Map);
    }
    throw Exception(_message(r));
  }
}
