import 'package:shared_preferences/shared_preferences.dart';

/// Stores the backend base URL (and remembers the last phone). Persisted via
/// shared_preferences so the server config survives restarts.
class SettingsService {
  static const _kBaseUrl = 'base_url';
  static const _kPhone = 'last_phone';

  // Default to the LAN backend; change on the Server Config screen.
  static const defaultBaseUrl = 'http://192.168.21.3:8000/api/v1';

  static Future<String> getBaseUrl() async {
    final p = await SharedPreferences.getInstance();
    return p.getString(_kBaseUrl) ?? defaultBaseUrl;
  }

  static Future<void> setBaseUrl(String url) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_kBaseUrl, url.trim());
  }

  static Future<String> getLastPhone() async {
    final p = await SharedPreferences.getInstance();
    return p.getString(_kPhone) ?? '';
  }

  static Future<void> setLastPhone(String phone) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_kPhone, phone.trim());
  }
}
