package com.f1.raceengineer.net

import org.json.JSONArray
import org.json.JSONObject

/**
 * 后端 Tool 层的 5 字段诚实信封（source_level/source/timestamp/unit/confidence）
 * + data + notes。data 因 Tool 而异：对象（session/telemetry/compare）、数组
 * （laps/sectors/corners/sessions）、或 null（无数据）。
 *
 * 薄客户端只透传展示，不新增计算；source_level 与 confidence 一路带到 UI，
 * 明确区分「实测（RAW/DERIVED）」与「推测（HYPOTHESIS）」（NO DATA → NO FACT）。
 */
data class ToolResult(
    val sourceLevel: String,
    val source: String,
    val timestamp: String,
    val unit: String,
    val confidence: String,
    val data: JSONObject?,
    val dataArray: JSONArray?,
    val notes: List<String>,
) {
    companion object {
        fun fromJson(json: JSONObject): ToolResult {
            val dataRaw = json.opt("data")
            val notesArr = json.optJSONArray("notes")
            val notes = buildList {
                if (notesArr != null) {
                    for (i in 0 until notesArr.length()) add(notesArr.optString(i))
                }
            }
            return ToolResult(
                sourceLevel = json.optString("source_level"),
                source = json.optString("source"),
                timestamp = json.optString("timestamp"),
                unit = json.optString("unit"),
                confidence = json.optString("confidence"),
                data = dataRaw as? JSONObject,
                dataArray = dataRaw as? JSONArray,
                notes = notes,
            )
        }
    }
}

/** 从 JSONObject 取可为 null 的 double 字段（org.json 对 null/missing 返回 NaN，需显式判空）。 */
fun JSONObject.optDoubleOrNull(key: String): Double? =
    if (isNull(key)) null else optDouble(key).takeUnless { it.isNaN() }

/** 从 JSONObject 取可为 null 的 int 字段。 */
fun JSONObject.optIntOrNull(key: String): Int? =
    if (isNull(key)) null else optInt(key)

/** 秒 → "m:ss.mmm" 圈速文本。 */
fun formatLapTime(seconds: Double?): String {
    if (seconds == null) return "—"
    val m = (seconds / 60).toInt()
    val s = seconds - m * 60
    return "%d:%06.3f".format(m, s)
}
