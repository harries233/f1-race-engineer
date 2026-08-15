package com.f1.raceengineer.net

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * 后端 REST 客户端（OkHttp，同步调用包在 IO 线程）。薄封装，只做 HTTP + JSON 解析，
 * 不缓存、不算数。REST 端点统一返回 ToolResult 信封；POST 端点（/api/compare 返回信封、
 * /api/ask 返回 {"answer": ...}）也归一到 JSONObject。
 */
class BackendClient(private val config: ServerConfig) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .build()

    /** GET → ToolResult 信封（失败抛异常，由调用方 runCatching 包装）。 */
    suspend fun get(path: String): ToolResult = withContext(Dispatchers.IO) {
        val req = Request.Builder().url(config.baseUrl + path).build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) throw BackendException("HTTP ${resp.code}")
            val body = resp.body?.string() ?: throw BackendException("空响应")
            ToolResult.fromJson(JSONObject(body))
        }
    }

    /** POST JSON → 原始 JSONObject（用于 /api/compare、/api/ask 等）。 */
    suspend fun post(path: String, payload: JSONObject): JSONObject = withContext(Dispatchers.IO) {
        val media = "application/json; charset=utf-8".toMediaType()
        val req = Request.Builder()
            .url(config.baseUrl + path)
            .post(payload.toString().toRequestBody(media))
            .build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) throw BackendException("HTTP ${resp.code}")
            JSONObject(resp.body?.string() ?: throw BackendException("空响应"))
        }
    }
}

class BackendException(message: String) : Exception(message)
