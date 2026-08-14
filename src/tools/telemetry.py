"""Tool：get_telemetry —— 读最新 Car Telemetry + Car Status 快照（RAW）。

从 `packet_car_telemetry`（速度/油门/刹车/挡位/转速/轮胎温度）与 `packet_car_status`
（燃油/ERS/轮胎状态）各取某车最新一帧，合并成单张快照 dict。数组字段（JSON 文本列）
反序列化回 list。
"""

from __future__ import annotations

import json

from store.schemas import Confidence, SourceLevel, now_utc
from tools.registry import Tool, ToolResult

_TELEMETRY_FIELDS = (
    "m_speed",
    "m_throttle",
    "m_steer",
    "m_brake",
    "m_clutch",
    "m_gear",
    "m_engineRPM",
    "m_drs",
    "m_revLightsPercent",
    "m_engineTemperature",
)
_TELEMETRY_JSON_ARRAY_FIELDS = (
    "m_brakesTemperature",
    "m_tyresSurfaceTemperature",
    "m_tyresInnerTemperature",
    "m_tyresPressure",
)
_STATUS_FIELDS = (
    "m_fuelMix",
    "m_frontBrakeBias",
    "m_fuelInTank",
    "m_fuelCapacity",
    "m_fuelRemainingLaps",
    "m_drsAllowed",
    "m_actualTyreCompound",
    "m_tyresAgeLaps",
    "m_ersStoreEnergy",
    "m_ersDeployMode",
)


def _latest_car_row(store, table: str, car_index: int, session_uid):
    where = "car_index = ?" + (" AND session_uid = ?" if session_uid is not None else "")
    params = (car_index,) + ((session_uid,) if session_uid is not None else ())
    rows = store.query(
        table, where=where, params=params, order_by="frame_identifier DESC", limit=1
    )
    return rows[0] if rows else None


def get_telemetry(store) -> Tool:
    """构造 get_telemetry Tool（依赖注入 store 只读句柄）。"""

    def handler(car_index: int, session_uid=None):
        tele = _latest_car_row(store, "packet_car_telemetry", car_index, session_uid)
        if tele is None:
            return ToolResult(
                source_level=SourceLevel.RAW,
                source="udp:packet:car_telemetry",
                timestamp=now_utc(),
                unit="raw",
                confidence=Confidence.HIGH,
                data=None,
                notes=[f"车辆 {car_index} 无 Car Telemetry 数据"],
            )
        status = _latest_car_row(store, "packet_car_status", car_index, session_uid)

        data = {"car_index": car_index}
        for f in _TELEMETRY_FIELDS:
            data[f] = tele.get(f)
        for f in _TELEMETRY_JSON_ARRAY_FIELDS:
            raw = tele.get(f)
            data[f] = json.loads(raw) if isinstance(raw, str) else raw
        if status is not None:
            for f in _STATUS_FIELDS:
                data[f] = status.get(f)

        return ToolResult(
            source_level=SourceLevel.RAW,
            source="udp:packet:car_telemetry",
            timestamp=tele.get("received_at"),
            unit="raw",
            confidence=Confidence.HIGH,
            data=data,
        )

    return Tool(
        name="get_telemetry",
        description="读取某车最新一帧的遥测快照：速度/油门/刹车/挡位/转速/轮胎 + 燃油/ERS（RAW 级，CarTelemetry 与 CarStatus 合并）。",
        parameters={
            "type": "object",
            "properties": {
                "car_index": {
                    "type": "integer",
                    "description": "车辆索引 0–23（默认 0 = 玩家车）",
                },
                "session_uid": {
                    "type": "integer",
                    "description": "会话 UID；缺省取最新",
                },
            },
            "required": ["car_index"],
        },
        handler=handler,
    )
