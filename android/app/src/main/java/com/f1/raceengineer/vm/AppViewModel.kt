package com.f1.raceengineer.vm

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.f1.raceengineer.net.BackendClient
import com.f1.raceengineer.net.ServerConfig
import com.f1.raceengineer.net.SocketStatus
import com.f1.raceengineer.net.TelemetrySocket
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

/**
 * 薄客户端的唯一状态聚合点。只读后端 + 展示，不新增计算。
 *
 * 数据来源三类：
 *  - REST（get_session/get_lap/get_sector/get_corner/list_sessions/list_experiments/
 *    list_recommendations/compare/ask）→ 一次性快照。
 *  - WS（/ws）→ 实时遥测（速度/挡位/转速/油门刹车…），按 packet 名缓存最新帧。
 *
 * 信封字段（source_level/confidence）随数据一起暴露给 UI，诚实区分实测与推测。
 */
data class ChatMessage(val role: Role, val text: String) {
    enum class Role { USER, ASSISTANT }
}

class AppViewModel(app: Application) : AndroidViewModel(app) {

    private val config = ServerConfig(app)
    private val client = BackendClient(config)
    val socket = TelemetrySocket(config)

    // 连接状态 / 实时遥测
    val socketStatus: StateFlow<SocketStatus> = socket.status
    val liveTelemetry: StateFlow<Map<String, JSONObject>> = socket.latest

    // 会话选择
    private val _sessions = MutableStateFlow<List<JSONObject>>(emptyList())
    val sessions: StateFlow<List<JSONObject>> = _sessions.asStateFlow()

    private val _sessionUid = MutableStateFlow<Long?>(null)
    val sessionUid: StateFlow<Long?> = _sessionUid.asStateFlow()

    // 车辆索引（默认 0 = 玩家车）
    private val _carIndex = MutableStateFlow(0)
    val carIndex: StateFlow<Int> = _carIndex.asStateFlow()

    // 仪表盘数据
    private val _session = MutableStateFlow<JSONObject?>(null)
    val session: StateFlow<JSONObject?> = _session.asStateFlow()

    private val _laps = MutableStateFlow<List<JSONObject>>(emptyList())
    val laps: StateFlow<List<JSONObject>> = _laps.asStateFlow()

    private val _sectors = MutableStateFlow<List<JSONObject>>(emptyList())
    val sectors: StateFlow<List<JSONObject>> = _sectors.asStateFlow()

    private val _corners = MutableStateFlow<List<JSONObject>>(emptyList())
    val corners: StateFlow<List<JSONObject>> = _corners.asStateFlow()

    // 对比页
    private val _compareResult = MutableStateFlow<JSONObject?>(null)
    val compareResult: StateFlow<JSONObject?> = _compareResult.asStateFlow()

    private val _experiments = MutableStateFlow<List<JSONObject>>(emptyList())
    val experiments: StateFlow<List<JSONObject>> = _experiments.asStateFlow()

    private val _recommendations = MutableStateFlow<List<JSONObject>>(emptyList())
    val recommendations: StateFlow<List<JSONObject>> = _recommendations.asStateFlow()

    // AI 对话
    private val _chat = MutableStateFlow<List<ChatMessage>>(emptyList())
    val chat: StateFlow<List<ChatMessage>> = _chat.asStateFlow()

    // 全局状态 / 提示
    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    private val _statusMessage = MutableStateFlow<String?>(null)
    val statusMessage: StateFlow<String?> = _statusMessage.asStateFlow()

    // 服务器配置（设置页读取/写入）
    val serverHost: String get() = config.host
    val serverPort: Int get() = config.port
    val serverConfigured: Boolean get() = config.isConfigured

    // ------------------------------------------------------------------
    // 连接
    // ------------------------------------------------------------------

    fun connect() {
        if (!config.isConfigured) return
        socket.connect()
        refresh()
    }

    fun disconnect() = socket.disconnect()

    fun saveServer(host: String, port: Int) {
        config.host = host
        config.port = port
        socket.disconnect()
        postStatus("已保存：${config.baseUrl}")
    }

    fun testConnection() {
        viewModelScope.launch {
            runCatching { client.get("/health") }
                .onSuccess { postStatus("连接成功，包数=${it.data?.optInt("packet_count")}") }
                .onFailure { postStatus("连接失败：${it.message ?: it.javaClass.simpleName}") }
        }
    }

    fun selectSession(uid: Long?) {
        _sessionUid.value = uid
        refresh()
    }

    fun setCarIndex(index: Int) {
        _carIndex.value = index
        refresh()
    }

    // ------------------------------------------------------------------
    // 数据加载
    // ------------------------------------------------------------------

    fun refresh() {
        loadSessions()
        loadSession()
        loadLaps()
        loadSectors()
        loadCorners()
        loadExperiments()
        loadRecommendations()
    }

    fun loadSessions() {
        viewModelScope.launch {
            runCatching { client.get("/api/sessions") }
                .onSuccess { _sessions.value = it.dataArray.toList() }
                .onFailure { postStatus("加载会话失败：${it.message}") }
        }
    }

    fun loadSession() {
        viewModelScope.launch {
            runCatching { client.get("/api/session${sessionQuery()}") }
                .onSuccess { _session.value = it.data }
                .onFailure { postStatus("加载 Session 失败：${it.message}") }
        }
    }

    fun loadLaps() {
        viewModelScope.launch {
            runCatching { client.get("/api/laps?car_index=${_carIndex.value}${sessionQuery("&")}") }
                .onSuccess { _laps.value = it.dataArray.toList() }
                .onFailure { postStatus("加载圈速失败：${it.message}") }
        }
    }

    fun loadSectors() {
        viewModelScope.launch {
            runCatching { client.get("/api/sectors?car_index=${_carIndex.value}${sessionQuery("&")}") }
                .onSuccess { _sectors.value = it.dataArray.toList() }
                .onFailure { postStatus("加载扇区失败：${it.message}") }
        }
    }

    fun loadCorners() {
        viewModelScope.launch {
            runCatching { client.get("/api/corners?car_index=${_carIndex.value}${sessionQuery("&")}") }
                .onSuccess { _corners.value = it.dataArray.toList() }
                .onFailure { postStatus("加载弯角失败：${it.message}") }
        }
    }

    fun loadExperiments() {
        viewModelScope.launch {
            runCatching { client.get("/api/experiments") }
                .onSuccess { _experiments.value = it.dataArray.toList() }
                .onFailure { postStatus("加载实验失败：${it.message}") }
        }
    }

    fun loadRecommendations() {
        viewModelScope.launch {
            runCatching { client.get("/api/recommendations") }
                .onSuccess { _recommendations.value = it.dataArray.toList() }
                .onFailure { postStatus("加载推荐失败：${it.message}") }
        }
    }

    // ------------------------------------------------------------------
    // 对比 / 对话
    // ------------------------------------------------------------------

    fun compare(baseline: List<Int>, test: List<Int>) {
        viewModelScope.launch {
            _busy.value = true
            val payload = JSONObject()
                .put("car_index", _carIndex.value)
                .put("baseline_laps", JSONArray(baseline))
                .put("test_laps", JSONArray(test))
            _sessionUid.value?.let { payload.put("session_uid", it) }
            runCatching { client.post("/api/compare", payload) }
                .onSuccess { _compareResult.value = it.optJSONObject("data") }
                .onFailure { postStatus("对比失败：${it.message}") }
            _busy.value = false
        }
    }

    fun ask(question: String) {
        val q = question.trim()
        if (q.isEmpty()) return
        _chat.value = _chat.value + ChatMessage(ChatMessage.Role.USER, q)
        viewModelScope.launch {
            _busy.value = true
            val payload = JSONObject().put("question", q)
            runCatching { client.post("/api/ask", payload) }
                .onSuccess {
                    _chat.value = _chat.value +
                        ChatMessage(ChatMessage.Role.ASSISTANT, it.optString("answer", "（无回答）"))
                }
                .onFailure {
                    _chat.value = _chat.value +
                        ChatMessage(ChatMessage.Role.ASSISTANT, "调用失败：${it.message}")
                }
            _busy.value = false
        }
    }

    fun clearChat() {
        _chat.value = emptyList()
    }

    // ------------------------------------------------------------------
    // 内部工具
    // ------------------------------------------------------------------

    /** session_uid 查询串；prefix 供在已有 `?car_index=…` 后追加时用 "&"。 */
    private fun sessionQuery(prefix: String = "?"): String =
        _sessionUid.value?.let { "${prefix}session_uid=$it" } ?: ""

    private fun postStatus(msg: String) {
        _statusMessage.value = msg
    }

    fun consumeStatus() {
        _statusMessage.value = null
    }
}

/** JSONArray → List<JSONObject>（逐项转换，供 UI 遍历）。 */
private fun JSONArray?.toList(): List<JSONObject> = buildList {
    if (this@toList == null) return@buildList
    for (i in 0 until this@toList.length()) {
        this@toList.optJSONObject(i)?.let { add(it) }
    }
}
