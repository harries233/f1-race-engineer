"""Tool：get_lap —— 由 Session History 构造完赛圈 LapRecord（DERIVED）。

数据源是 `packet_session_history`（全局包，按车轮询，`m_carIdx` 标识该帧描述的车）。
其 `m_lapHistoryData` 是 JSON 文本列（数组 100 项，仅前 `m_numLaps` 项为完赛圈）。
本 Tool 重建 `LapHistoryData` 后调 L4 `analysis.lap.build_lap_record` 计算圈速/分段时间
/有效性 —— AI 层不自己算数，只读 L4 的确定性结果。
"""

from __future__ import annotations

import json

from analysis.lap import build_lap_record
from protocol.f1_25_2026.payload import LapHistoryData
from store.schemas import Confidence, LapRecord, SourceLevel, now_utc
from tools.registry import Tool, ToolResult


def completed_laps(store, car_index: int, session_uid=None) -> list[LapRecord]:
    """读某车最新 Session History，重建全部完赛圈 LapRecord（L4 计算后）。

    供 get_lap / compare / validate_setup 复用，保证「圈号 → 圈速」口径一致。
    无数据返回空列表。
    """
    where = "m_carIdx = ?" + (" AND session_uid = ?" if session_uid is not None else "")
    params = (car_index,) + ((session_uid,) if session_uid is not None else ())
    rows = store.query(
        "packet_session_history",
        where=where,
        params=params,
        order_by="frame_identifier DESC",
        limit=1,
    )
    if not rows:
        return []

    row = rows[0]
    num_laps = row.get("m_numLaps") or 0
    raw_history = row.get("m_lapHistoryData")
    entries = json.loads(raw_history) if isinstance(raw_history, str) else (raw_history or [])

    records = []
    for i, entry in enumerate(entries[:num_laps]):
        lap_history = LapHistoryData(**entry)
        records.append(
            build_lap_record(
                lap_history,
                lap_number=i + 1,
                session_uid=row.get("session_uid"),
                received_at=row.get("received_at"),
            )
        )
    return records


def get_lap(store) -> Tool:
    """构造 get_lap Tool（依赖注入 store 只读句柄）。"""

    def handler(car_index: int, session_uid=None, lap_number=None):
        records = completed_laps(store, car_index, session_uid)
        if not records:
            return ToolResult(
                source_level=SourceLevel.DERIVED,
                source="calc:lap_metrics",
                timestamp=now_utc(),
                unit="s",
                confidence=Confidence.HIGH,
                data=[],
                notes=[f"车辆 {car_index} 无 Session History 数据"],
            )

        data = [
            record.model_dump()
            for record in records
            if lap_number is None or record.lap_number == lap_number
        ]
        return ToolResult(
            source_level=SourceLevel.DERIVED,
            source="calc:lap_metrics",
            timestamp=records[0].timestamp,
            unit="s",
            confidence=Confidence.HIGH,
            data=data,
            notes=["圈号按 lapHistoryData 数组位置(1-based)推导"],
        )

    return Tool(
        name="get_lap",
        description="读取某车已完赛圈的圈速与三段分段时间及有效性（DERIVED，由 Session History 经 L4 计算）。",
        parameters={
            "type": "object",
            "properties": {
                "car_index": {
                    "type": "integer",
                    "description": "车辆索引 0–23（Session History 按车轮询，m_carIdx 标识该车）",
                },
                "session_uid": {
                    "type": "integer",
                    "description": "会话 UID；缺省取最新",
                },
                "lap_number": {
                    "type": "integer",
                    "description": "只取某圈；缺省返回全部完赛圈",
                },
            },
            "required": ["car_index"],
        },
        handler=handler,
    )
