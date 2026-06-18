import 'package:flutter/services.dart';
import '../models.dart';

/// Bridge to the native Hopeland RFID SDK (Android/Kotlin).
///
/// Flutter cannot call the Hopeland Java/Kotlin SDK directly — the native side
/// (android/.../MainActivity.kt) implements these channels and drives the SDK.
/// Until the SDK is integrated there, [connect] returns false and [tagStream]
/// emits nothing; use the manual-add field on the Scan screen to test.
class RfidService {
  RfidService._();
  static final RfidService instance = RfidService._();

  static const _methods = MethodChannel('mtag_scanner/rfid');
  static const _events = EventChannel('mtag_scanner/rfid/tags');

  Stream<TagRead>? _stream;

  /// Connect/initialise the reader. Returns true if ready.
  Future<bool> connect() async {
    try {
      final ok = await _methods.invokeMethod<bool>('connect');
      return ok ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false; // native bridge not wired yet
    }
  }

  Future<void> startInventory() async {
    try {
      await _methods.invokeMethod('start');
    } catch (_) {/* surfaced via connect() state */}
  }

  Future<void> stopInventory() async {
    try {
      await _methods.invokeMethod('stop');
    } catch (_) {}
  }

  Future<void> disconnect() async {
    try {
      await _methods.invokeMethod('disconnect');
    } catch (_) {}
  }

  /// Stream of tag reads pushed by the native SDK callback (EPC + TID).
  Stream<TagRead> get tagStream {
    _stream ??= _events
        .receiveBroadcastStream()
        .map((e) => TagRead.fromMap(Map<dynamic, dynamic>.from(e as Map)));
    return _stream!;
  }
}
