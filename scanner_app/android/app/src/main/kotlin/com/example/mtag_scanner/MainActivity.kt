package com.example.mtag_scanner

import android.os.Handler
import android.os.Looper
import com.pda.rfid.EPCModel
import com.pda.rfid.IAsynchronousMessage
import com.pda.rfid.uhf.UHFReader
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel
import java.util.concurrent.Executors

/**
 * Flutter ↔ Hopeland UHF SDK bridge for the HY820.
 *
 * SDK flow (from the PDAExample sample):
 *   UHFReader.getUHFInstance().OpenConnect(this)   // this = IAsynchronousMessage
 *   UHFReader._Tag6C.GetEPC_TID(antenna, 1)        // continuous EPC + TID read
 *   UHFReader._Config.Stop() / .CloseConnect()
 *   tags arrive in OutPutEPC(EPCModel) → _EPC / _TID
 */
class MainActivity : FlutterActivity(), IAsynchronousMessage {

    private val methodChannelName = "mtag_scanner/rfid"
    private val eventChannelName = "mtag_scanner/rfid/tags"

    private var events: EventChannel.EventSink? = null
    private val main = Handler(Looper.getMainLooper())
    // Background executor for connect/stop/disconnect (must be separate from the
    // inventory thread so Stop() can interrupt a blocking GetEPC_TID).
    private val io = Executors.newSingleThreadExecutor()
    private val antenna = 1
    @Volatile private var connected = false

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, methodChannelName)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "connect" -> io.execute {
                        val ok = try {
                            val r = UHFReader.getUHFInstance().OpenConnect(this)
                            if (r) {
                                try { UHFReader._Config.Stop() } catch (_: Exception) {}
                                // Perf: throttle duplicate tag uploads — the same tag
                                // re-reports at most ~every 500ms (new tags still report
                                // immediately, so no accuracy loss), cutting callback flood.
                                try { UHFReader._Config.SetTagUpdateParam(500, 0) } catch (_: Exception) {}
                            }
                            connected = r
                            r
                        } catch (e: Exception) {
                            connected = false
                            false
                        }
                        main.post { result.success(ok) }
                    }

                    "start" -> {
                        // GetEPC_TID may block until Stop(); run on its own thread.
                        Thread {
                            try {
                                UHFReader._Tag6C.GetEPC_TID(antenna, 1)
                            } catch (_: Exception) {}
                        }.start()
                        result.success(null)
                    }

                    "stop" -> io.execute {
                        try { UHFReader._Config.Stop() } catch (_: Exception) {}
                        main.post { result.success(null) }
                    }

                    "disconnect" -> io.execute {
                        try { UHFReader._Config.Stop() } catch (_: Exception) {}
                        try { UHFReader._Config.CloseConnect() } catch (_: Exception) {}
                        connected = false
                        main.post { result.success(null) }
                    }

                    else -> result.notImplemented()
                }
            }

        EventChannel(flutterEngine.dartExecutor.binaryMessenger, eventChannelName)
            .setStreamHandler(object : EventChannel.StreamHandler {
                override fun onListen(args: Any?, sink: EventChannel.EventSink?) { events = sink }
                override fun onCancel(args: Any?) { events = null }
            })
    }

    /** Hopeland SDK tag callback (runs on an SDK thread). */
    override fun OutPutEPC(model: EPCModel) {
        val tid = model._TID ?: ""
        val epc = model._EPC ?: ""
        if (tid.isEmpty() && epc.isEmpty()) return
        main.post { events?.success(mapOf("tid" to tid, "epc" to epc)) }
    }

    override fun onDestroy() {
        try { UHFReader._Config.Stop() } catch (_: Exception) {}
        try { if (connected) UHFReader._Config.CloseConnect() } catch (_: Exception) {}
        io.shutdownNow()
        super.onDestroy()
    }
}
