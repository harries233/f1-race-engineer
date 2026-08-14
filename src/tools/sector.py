"""Tool：get_sector —— 某车完赛圈的 sector 分段时间 + 关键速度点（DERIVED）。

分段时间来自 Session History（LapRecord.sector1/2/3，L4 已换算）；速度点来自把
CarTelemetry 速度流按 LapData 的 `m_sector` 切分（analysis.sector_segment），再经
`sector_speed_metrics` 归约 entry/min/exit。速度点需跨 packet 时间对齐，属近似，故
置信度 MEDIUM，并在 notes 声明。
"""

from __future__ import annotations

from analysis.sector import build_sector_record
from analysis.sector_segment import LapFrame, SpeedFrame, segment_speeds_by_sector
from store.schemas import Confidence, SourceLevel, now_utc
from tools.lap import completed_laps
from tools.registry import Tool, ToolResult

_SECTOR_ATTRS = ("sector1", "sector2", "sector3")


def get_sector(store) -> Tool:
    """构造 get_sector Tool（依赖注入 store 只读句柄）。"""

    def handler(car_index: int, lap_number=None, session_uid=None) -> ToolResult:
        laps = completed_laps(store, car_index, session_uid)
        if not laps:
            return ToolResult(
                source_level=SourceLevel.DERIVED,
                source="calc:sector_metrics",
                timestamp=now_utc(),
                unit="km/h",
                confidence=Confidence.MEDIUM,
                data=[],
                notes=[f"车辆 {car_index} 无完赛圈数据"],
            )

        lap_times = {r.lap_number: r for r in laps}
        target_laps = (
            [lap_number] if lap_number is not None else sorted(lap_times.keys())
        )
        if lap_number is not None and lap_number not in lap_times:
            return ToolResult(
                source_level=SourceLevel.DERIVED,
                source="calc:sector_metrics",
                timestamp=now_utc(),
                unit="km/h",
                confidence=Confidence.MEDIUM,
                data=[],
                notes=[f"圈 {lap_number} 无完赛圈记录"],
            )

        speed_frames = _read_speed_frames(store, car_index, session_uid)
        lap_frames = _read_lap_frames(store, car_index, session_uid)
        grouped = segment_speeds_by_sector(speed_frames, lap_frames)

        records = []
        for ln in target_laps:
            lap = lap_times[ln]
            for sector_index in (0, 1, 2):
                sector_time = getattr(lap, _SECTOR_ATTRS[sector_index])
                if sector_time is None:
                    continue
                record = build_sector_record(
                    lap_number=ln,
                    sector_index=sector_index,
                    sector_time=sector_time,
                    speeds=grouped.get((ln, sector_index), []),
                    received_at=lap.timestamp,
                )
                records.append(record.model_dump())

        return ToolResult(
            source_level=SourceLevel.DERIVED,
            source="calc:sector_metrics",
            timestamp=laps[0].timestamp,
            unit="km/h",
            confidence=Confidence.MEDIUM,
            data=records,
            notes=[
                "速度点经 CarTelemetry 与 LapData 跨 packet 时间对齐（m_overallFrameIdentifier）",
                "sector 标签用游戏自报 m_sector；切换瞬间可能错位 1 帧，属近似",
            ],
        )

    return Tool(
        name="get_sector",
        description="读取某车完赛圈的分段时间与 entry/min/exit 关键速度点（速度点 DERIVED，跨 packet 时间对齐）。",
        parameters={
            "type": "object",
            "properties": {
                "car_index": {"type": "integer", "description": "车辆索引 0–23"},
                "lap_number": {
                    "type": "integer",
                    "description": "只取某圈；缺省返回全部完赛圈",
                },
                "session_uid": {"type": "integer", "description": "会话 UID；缺省取最新"},
            },
            "required": ["car_index"],
        },
        handler=handler,
    )


def _read_speed_frames(store, car_index: int, session_uid) -> list[SpeedFrame]:
    where = "car_index = ?" + (" AND session_uid = ?" if session_uid is not None else "")
    params = (car_index,) + ((session_uid,) if session_uid is not None else ())
    rows = store.query(
        "packet_car_telemetry",
        where=where,
        params=params,
        order_by="overall_frame_identifier",
    )
    return [
        SpeedFrame(frame_id=row["overall_frame_identifier"], speed=float(row["m_speed"]))
        for row in rows
        if row.get("m_speed") is not None
    ]


def _read_lap_frames(store, car_index: int, session_uid) -> list[LapFrame]:
    where = "car_index = ?" + (" AND session_uid = ?" if session_uid is not None else "")
    params = (car_index,) + ((session_uid,) if session_uid is not None else ())
    rows = store.query(
        "packet_lap_data",
        where=where,
        params=params,
        order_by="overall_frame_identifier",
    )
    return [
        LapFrame(
            frame_id=row["overall_frame_identifier"],
            lap_num=int(row["m_currentLapNum"]),
            sector=int(row["m_sector"]),
        )
        for row in rows
        if row.get("m_currentLapNum") is not None and row.get("m_sector") is not None
    ]
