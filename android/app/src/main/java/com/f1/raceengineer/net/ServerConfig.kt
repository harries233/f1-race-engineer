package com.f1.raceengineer.net

import android.content.Context

/**
 * 后端连接配置：主机 + 端口，SharedPreferences 持久化。
 *
 * 薄客户端只连局域网后端（FastAPI + UDP receiver），host 由用户在设置页填
 * （如 `192.168.1.10`），不硬编码。缺省 host 为空 = 未配置，UI 会引导填写。
 */
class ServerConfig(context: Context) {

    private val prefs = context.getSharedPreferences("server", Context.MODE_PRIVATE)

    var host: String
        get() = prefs.getString("host", "") ?: ""
        set(value) {
            prefs.edit().putString("host", value.trim()).apply()
        }

    var port: Int
        get() = prefs.getInt("port", 8000)
        set(value) {
            prefs.edit().putInt("port", value).apply()
        }

    val isConfigured: Boolean
        get() = host.isNotBlank()

    val baseUrl: String
        get() = "http://$host:$port"

    val wsUrl: String
        get() = "ws://$host:$port/ws"
}
