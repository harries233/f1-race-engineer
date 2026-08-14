"""Tool：get_session —— 读最新 Session 上下文（RAW）。

从 `packet_session` 结构化表取最新一帧，返回天气/温度/赛道/会话类型等上下文。
字段值按官方 Spec 原始整数/浮点返回；枚举字段（weather/sessionType/trackId）未做
名称映射，标 TODO(verify)。
"""

from __future__ import annotations

from store.schemas import Confidence, SourceLevel, now_utc
from tools.registry import Tool, ToolResult

_SESSION_FIELDS = (
    "m_weather",
    "m_trackTemperature",
    "m_airTemperature",
    "m_sessionType",
    "m_trackId",
    "m_totalLaps",
    "m_trackLength",
    "m_sessionDuration",
    "m_pitSpeedLimit",
    "m_safetyCarStatus",
    "m_networkGame",
    "m_numWeatherForecastSamples",
    "m_forecastAccuracy",
)


def get_session(store) -> Tool:
    """构造 get_session Tool（依赖注入 store 只读句柄）。"""

    def handler(session_uid=None):
        rows = store.query(
            "packet_session",
            where="session_uid = ?" if session_uid is not None else "1=1",
            params=(session_uid,) if session_uid is not None else (),
            order_by="frame_identifier DESC",
            limit=1,
        )
        if not rows:
            return ToolResult(
                source_level=SourceLevel.RAW,
                source="udp:packet:session",
                timestamp=now_utc(),
                unit="raw",
                confidence=Confidence.HIGH,
                data=None,
                notes=["库中无 Session 数据"],
            )
        row = rows[0]
        data = {f: row.get(f) for f in _SESSION_FIELDS}
        data["session_uid"] = row.get("session_uid")
        data["frame_identifier"] = row.get("frame_identifier")
        return ToolResult(
            source_level=SourceLevel.RAW,
            source="udp:packet:session",
            timestamp=row.get("received_at"),
            unit="raw",
            confidence=Confidence.HIGH,
            data=data,
            notes=["枚举字段(weather/sessionType/trackId)为原始整数，未做名称映射 TODO(verify)"],
        )

    return Tool(
        name="get_session",
        description="读取指定会话（缺省最新）的 Session 上下文：天气、温度、赛道、会话类型、圈数等（RAW 级）。",
        parameters={
            "type": "object",
            "properties": {
                "session_uid": {
                    "type": "integer",
                    "description": "会话 UID；缺省取最新一帧会话",
                },
            },
        },
        handler=handler,
    )
