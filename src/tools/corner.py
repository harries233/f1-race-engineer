"""Tool：get_corner —— 某车某圈的逐弯指标（DERIVED，PHASE 11）。

弯角几何来自独立赛道数据层（`track` 模块，lapDistance 区间估算）。遥测流
（CarTelemetry）与 lapDistance（LapData）靠 `m_overallFrameIdentifier` 时间对齐，
再按弯角区间切分，调 L4 `analysis.corner` 归约 entry/mid/exit 指标。

诚实性：
  - 弯角 lapDistance 边界为估算（HYPOTHESIS）→ 置信度 MEDIUM。
  - track_id 目前仅内置 "shanghai"；由 SessionData.m_trackId（整数）自动解析赛道
    的映射表待官方 Spec 确认，本 phase 不接入（TODO(verify)）。
"""

from __future__ import annotations

from analysis.corner import (
    LapDistanceFrame,
    TelemetryFrame,
    align_to_lap_distance,
    assign_corners,
    build_corner_record,
)
from store.schemas import Confidence, SourceLevel, now_utc
from tools.registry import Tool, ToolResult
from track import get_track, list_tracks

_DEFAULT_TRACK = "shanghai"


def get_corner(store) -> Tool:
    """构造 get_corner Tool（依赖注入 store 只读句柄）。"""

    def handler(car_index: int, lap_number=None, track_id=None, session_uid=None) -> ToolResult:
        tid = track_id or _DEFAULT_TRACK
        track = get_track(tid)
        if track is None:
            return ToolResult(
                source_level=SourceLevel.DERIVED,
                source="calc:corner_metrics",
                timestamp=now_utc(),
                unit="km/h",
                confidence=Confidence.MEDIUM,
                data=[],
                notes=[f"未知赛道 {tid}；当前内置 {[t.track_id for t in list_tracks()]}"],
            )

        telemetry, received_at = _read_telemetry(store, car_index, session_uid)
        laps = _read_lap_distance(store, car_index, session_uid)
        samples = align_to_lap_distance(telemetry, laps)
        if not samples:
            return ToolResult(
                source_level=SourceLevel.DERIVED,
                source="calc:corner_metrics",
                timestamp=received_at or now_utc(),
                unit="km/h",
                confidence=Confidence.MEDIUM,
                data=[],
                notes=[f"车辆 {car_index} 无遥测 / 圈里程数据（无法分段）"],
            )

        lap_nums = {s.lap_num for s in samples}
        if lap_number is not None and lap_number not in lap_nums:
            return ToolResult(
                source_level=SourceLevel.DERIVED,
                source="calc:corner_metrics",
                timestamp=received_at or now_utc(),
                unit="km/h",
                confidence=Confidence.MEDIUM,
                data=[],
                notes=[f"圈 {lap_number} 无遥测 / 圈里程样本"],
            )

        target_laps = [lap_number] if lap_number is not None else sorted(lap_nums)
        records = []
        for ln in target_laps:
            lap_samples = [s for s in samples if s.lap_num == ln]
            grouped = assign_corners(lap_samples, track)
            for corner_number in sorted(grouped):
                records.append(
                    build_corner_record(
                        track=track,
                        corner_number=corner_number,
                        samples=grouped[corner_number],
                        lap_number=ln,
                        received_at=received_at or now_utc(),
                    ).model_dump()
                )

        return ToolResult(
            source_level=SourceLevel.DERIVED,
            source="calc:corner_metrics",
            timestamp=received_at or now_utc(),
            unit="km/h",
            confidence=Confidence.MEDIUM,
            data=records,
            notes=[
                "弯角 lapDistance 边界为估算(HYPOTHESIS)，未经真实数据标定",
                "CarTelemetry 与 LapData 跨 packet 时间对齐（m_overallFrameIdentifier）",
                "entry_brake_pressure 单位 %、entry_braking_point/brake_release 单位米(沿赛道里程)",
                "time_loss_phase/exit_traction/mid_stability 需参考圈/车轮滑移/稳定性定义，本 phase 不产出(None)",
            ],
        )

    return Tool(
        name="get_corner",
        description=(
            "读取某车某圈的逐弯指标（entry/mid/exit 速度、刹车点/刹车力度、转向、油门、挡位；DERIVED，"
            "弯角边界为估算 HYPOTHESIS）。track_id 目前仅内置 shanghai。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "car_index": {"type": "integer", "description": "车辆索引 0–23"},
                "lap_number": {
                    "type": "integer",
                    "description": "只取某圈；缺省返回全部出现过的圈",
                },
                "track_id": {
                    "type": "string",
                    "description": "赛道 id（当前仅 shanghai）；缺省 shanghai",
                },
                "session_uid": {"type": "integer", "description": "会话 UID；缺省取最新"},
            },
            "required": ["car_index"],
        },
        handler=handler,
    )


def _read_telemetry(store, car_index: int, session_uid) -> tuple[list[TelemetryFrame], str | None]:
    where = "car_index = ?" + (" AND session_uid = ?" if session_uid is not None else "")
    params = (car_index,) + ((session_uid,) if session_uid is not None else ())
    rows = store.query(
        "packet_car_telemetry",
        where=where,
        params=params,
        order_by="overall_frame_identifier",
    )
    frames = [
        TelemetryFrame(
            frame_id=row["overall_frame_identifier"],
            speed=float(row["m_speed"]),
            throttle=float(row["m_throttle"]),
            steer=float(row["m_steer"]),
            brake=float(row["m_brake"]),
            gear=int(row["m_gear"]),
        )
        for row in rows
        if row.get("m_speed") is not None
    ]
    return frames, (rows[0].get("received_at") if rows else None)


def _read_lap_distance(store, car_index: int, session_uid) -> list[LapDistanceFrame]:
    where = "car_index = ?" + (" AND session_uid = ?" if session_uid is not None else "")
    params = (car_index,) + ((session_uid,) if session_uid is not None else ())
    rows = store.query(
        "packet_lap_data",
        where=where,
        params=params,
        order_by="overall_frame_identifier",
    )
    return [
        LapDistanceFrame(
            frame_id=row["overall_frame_identifier"],
            lap_num=int(row["m_currentLapNum"]),
            lap_distance=float(row["m_lapDistance"]),
        )
        for row in rows
        if row.get("m_currentLapNum") is not None and row.get("m_lapDistance") is not None
    ]
