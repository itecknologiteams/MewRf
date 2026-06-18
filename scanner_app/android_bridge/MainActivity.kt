package com.example.mtag_scanner

import android.os.Handler
import android.os.Looper
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel

/**
 * Native bridge between Flutter and the Hopeland UHF SDK (HY820).
 *
 * Place this at:
 *   android/app/src/main/kotlin/com/example/mtag_scanner/MainActivity.kt
 * (match the package to your flutter-created project; adjust `package` above.)
 *
 * Channels (must match lib/services/rfid_service.dart):
 *   MethodChannel "mtag_scanner/rfid"        → connect / start / stop / disconnect
 *   EventChannel  "mtag_scanner/rfid/tags"   → stream of {tid, epc} maps
 *
 * >>> FILL THE `TODO(SDK)` BLOCKS using the Hopeland Android SDK + its sample
 *     code. The flow mirrors the Python SDK we have for the gate reader:
 *       init reader → set extended TID read → start inventory →
 *       on each tag callback push {tid, epc} to the EventChannel sink.
 */
class MainActivity : FlutterActivity() {

    private val methodChannel = "mtag_scanner/rfid"
    private val eventChannel = "mtag_scanner/rfid/tags"
    private var events: EventChannel.EventSink? = null
    private val main = Handler(Looper.getMainLooper())

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, methodChannel)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "connect" -> result.success(connectReader())
                    "start" -> { startInventory(); result.success(null) }
                    "stop" -> { stopInventory(); result.success(null) }
                    "disconnect" -> { disconnectReader(); result.success(null) }
                    else -> result.notImplemented()
                }
            }

        EventChannel(flutterEngine.dartExecutor.binaryMessenger, eventChannel)
            .setStreamHandler(object : EventChannel.StreamHandler {
                override fun onListen(args: Any?, sink: EventChannel.EventSink?) { events = sink }
                override fun onCancel(args: Any?) { events = null }
            })
    }

    /** Push a tag read to Flutter (call from the SDK's tag callback). */
    private fun emitTag(tid: String, epc: String) {
        main.post { events?.success(mapOf("tid" to tid, "epc" to epc)) }
    }

    // ── Hopeland SDK integration ────────────────────────────────────────────

    private fun connectReader(): Boolean {
        // TODO(SDK): initialise the HY820 reader via the Hopeland Android SDK.
        //   e.g. create the reader instance, open the connection (built-in UHF
        //   module — usually a fixed serial/USB path, not TCP for the handheld),
        //   then enable extended TID read (analog of the Python:
        //     paramSet(WO_RFIDReadExtended, [ReadExtendedArea_Model(TID,0,6,"")]))
        //   Register the tag callback so it calls emitTag(tid, epc).
        // Return true if the reader is ready, false otherwise.
        return false
    }

    private fun startInventory() {
        // TODO(SDK): start continuous inventory. On each tag the SDK callback
        //   should call: emitTag(tag.tid, tag.epc)
    }

    private fun stopInventory() {
        // TODO(SDK): stop inventory.
    }

    private fun disconnectReader() {
        // TODO(SDK): stop inventory (if running) + close/release the reader.
        events = null
    }
}
