package com.f1.raceengineer.net

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * WS 实时遥测订阅（OkHttp WebSocket）。
 *
 * 后端 /ws 建立即发一条 hello，之后每帧广播 `{type:"telemetry", packet, data, ...}`。
 * 本层只按 packet 名缓存最新一帧（session/lap_data/car_telemetry/car_status），
 * 供仪表盘 UI 以 StateFlow 订阅；不做计算、不做二次解析（嵌套 JSON 列原样透传）。
 */
enum class SocketStatus { DISCONNECTED, CONNECTING, CONNECTED }

class TelemetrySocket(private val config: ServerConfig) {

    private val client = OkHttpClient.Builder()
        .pingInterval(20, TimeUnit.SECONDS)
        .build()
    private var socket: WebSocket? = null

    private val _status = MutableStateFlow(SocketStatus.DISCONNECTED)
    val status: StateFlow<SocketStatus> = _status.asStateFlow()

    /** packet 名 → 最新一帧 data（JSONObject，原样透传）。 */
    private val _latest = MutableStateFlow<Map<String, JSONObject>>(emptyMap())
    val latest: StateFlow<Map<String, JSONObject>> = _latest.asStateFlow()

    fun connect() {
        if (socket != null) return
        _status.value = SocketStatus.CONNECTING
        val req = Request.Builder().url(config.wsUrl).build()
        socket = client.newWebSocket(req, listener)
    }

    fun disconnect() {
        socket?.close(1000, "client close")
        socket = null
        _status.value = SocketStatus.DISCONNECTED
    }

    private val listener = object : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            _status.value = SocketStatus.CONNECTED
        }

        override fun onMessage(webSocket: WebSocket, text: String) {
            runCatching {
                val obj = JSONObject(text)
                if (obj.optString("type") != "telemetry") return
                val packet = obj.optString("packet")
                val data = obj.optJSONObject("data")
                if (packet.isNotEmpty() && data != null) {
                    _latest.value = _latest.value + (packet to data)
                }
            }
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            socket = null
            _status.value = SocketStatus.DISCONNECTED
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            socket = null
            _status.value = SocketStatus.DISCONNECTED
        }
    }
}
