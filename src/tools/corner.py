"""Tool：get_corner —— 某车某圈的逐弯指标（DERIVED，PHASE 11 + PHASE 13）。

弯角几何来自独立赛道数据层（`track` 模块，lapDistance 区间估算）。遥测流
（CarTelemetry）与 lapDistance（LapData）靠 `m_overallFrameIdentifier` 时间对齐，
再按弯角区间切分，调 L4 `analysis.corner` 归约 entry/mid/exit 指标。

PHASE 13 补齐三项进阶指标：
  - mid_stability：中段转向抖动（corner_metrics 内确定性推导）。
  - time_loss_phase：参考圈对比——每弯以「apex 速度最快的一圈」为参考，本圈在
    ENTRY/MID/EXIT 哪一相速度损失最大。
  - exit_traction：MotionEx（packet 13，player-car-only）驱动轮 slip ratio 出口牵引评分。

诚实性：
  - 弯角 lapDistance 边界为估算（HYPOTHESIS）→ 置信度 MEDIUM。
  - MotionEx 是玩家车专属数据，exit_traction 只反映玩家车（非任意 car_index）。
  - track_id 缺省时由最新 Session 的 m_trackId 经官方 Track ID 附录解析；无映射/无
    Session 数据时回退 "shanghai"。
"""

from __future__ import annotations

import json

from analysis.corner import (
    LapDistanceFrame,
    TelemetryFrame,
    align_to_lap_distance,
    assign_corners,
    build_corner_record,
    corner_metrics,
    phase_time_loss,
)
from analysis.corner_advanced import (
    MotionExFrame,
    align_motion_ex_to_lap_distance,
    exit_traction,
)
from store.schemas import Confidence, SourceLevel, now_utc
from tools.registry import Tool, ToolResult
from track import get_track, list_tracks, track_id_for

_DEFAULT_TRACK = "shanghai"


def get_corner(store) -> Tool:
    """构造 get_corner Tool（依赖注入 store 只读句柄）。"""

    def handler(car_index: int, lap_number=None, track_id=None, session_uid=None) -> ToolResult:
        tid, resolve_notes = _resolve_track(store, track_id)
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

        lap_nums = sorted({s.lap_num for s in samples})
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

        target_laps = [lap_number] if lap_number is not None else lap_nums

        # 逐 (lap, corner) 分组样本 + 归约指标
        grouped = _group_by_lap_corner(samples, lap_nums, track)
        metrics = {k: corner_metrics(cs) for k, cs in grouped.items()}
        corners_present = sorted({cn for (_, cn) in grouped})

        # 每弯参考圈 = apex 速度最快的一圈（min_speed 最大，tie → exit_speed）
        ref_lap = {
            cn: max(
                ((ln, metrics[(ln, cn)]) for ln in lap_nums if (ln, cn) in grouped),
                key=lambda t: (t[1].min_speed, t[1].exit_speed),
            )[0]
            for cn in corners_present
        }

        # MotionEx 出口牵引（player-car-only）
        motion_frames = _read_motion_ex(store, session_uid)
        motion_samples = align_motion_ex_to_lap_distance(motion_frames, laps)
        motion_by_lap_corner = _group_motion_by_lap_corner(motion_samples, lap_nums, track)

        records = []
        for ln in target_laps:
            for cn in corners_present:
                if (ln, cn) not in grouped:
                    continue
                cs = grouped[(ln, cn)]
                m = metrics[(ln, cn)]
                apex_lap_distance = min(cs, key=lambda s: s.speed).lap_distance
                tlp = phase_time_loss(m, metrics[(ref_lap[cn], cn)])
                et = exit_traction(motion_by_lap_corner.get((ln, cn), []), apex_lap_distance)
                records.append(
                    build_corner_record(
                        track=track,
                        corner_number=cn,
                        samples=cs,
                        lap_number=ln,
                        received_at=received_at or now_utc(),
                        time_loss_phase=tlp,
                        exit_traction=et,
                    ).model_dump()
                )

        notes = [
            "弯角 lapDistance 边界为估算(HYPOTHESIS)，未经真实数据标定",
            "CarTelemetry 与 LapData 跨 packet 时间对齐（m_overallFrameIdentifier）",
            "entry_brake_pressure 单位 %、entry_braking_point/brake_release 单位米(沿赛道里程)",
            "time_loss_phase：每弯以 apex 速度最快的一圈为参考圈，比较 ENTRY/MID/EXIT 三相速度",
            "mid_stability：中段 1/3 转向抖动 1-pstdev(steer)，越接近 1 越稳（确定性代理定义）",
            "exit_traction：MotionEx 驱动轮 slip ratio 出口评分（player-car-only，1=无滑移）",
        ]
        notes.extend(resolve_notes)

        return ToolResult(
            source_level=SourceLevel.DERIVED,
            source="calc:corner_metrics",
            timestamp=received_at or now_utc(),
            unit="km/h",
            confidence=Confidence.MEDIUM,
            data=records,
            notes=notes,
        )

    return Tool(
        name="get_corner",
        description=(
            "读取某车某圈的逐弯指标（entry/mid/exit 速度、刹车点/力度、转向、油门、挡位、"
            "中段稳定性、参考圈对比的时间损失相位、出口牵引；DERIVED，弯角边界为估算 HYPOTHESIS）。"
            "track_id 缺省由 Session m_trackId 解析，当前仅内置 shanghai 几何。"
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
                    "description": "赛道 id（缺省由 Session m_trackId 解析；当前仅 shanghai）",
                },
                "session_uid": {"type": "integer", "description": "会话 UID；缺省取最新"},
            },
            "required": ["car_index"],
        },
        handler=handler,
    )


def _resolve_track(store, track_id) -> tuple[str, list[str]]:
    """缺省 track_id 时由最新 Session m_trackId 解析；返回 (track_id, notes)。"""
    if track_id is not None:
        return track_id, []
    rows = store.query(
        "packet_session", where="1=1", order_by="frame_identifier DESC", limit=1
    )
    if rows and rows[0].get("m_trackId") is not None:
        m_tid = int(rows[0]["m_trackId"])
        slug = track_id_for(m_tid)
        if slug:
            return slug, [f"由 Session m_trackId={m_tid} 解析为 {slug}（官方 Track ID 附录）"]
        return _DEFAULT_TRACK, [f"Session m_trackId={m_tid} 无映射，回退 {_DEFAULT_TRACK}"]
    return _DEFAULT_TRACK, ["无 Session 数据，track_id 缺省 shanghai"]


def _group_by_lap_corner(samples, lap_nums, track) -> dict:
    grouped = {}
    for ln in lap_nums:
        lap_samples = [s for s in samples if s.lap_num == ln]
        for cn, cs in assign_corners(lap_samples, track).items():
            grouped[(ln, cn)] = cs
    return grouped


def _group_motion_by_lap_corner(motion_samples, lap_nums, track) -> dict:
    grouped = {}
    for ln in lap_nums:
        ms = [m for m in motion_samples if m.lap_num == ln]
        for cn, cs in assign_corners(ms, track).items():
            grouped[(ln, cn)] = cs
    return grouped


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


def _read_motion_ex(store, session_uid) -> list[MotionExFrame]:
    """读 MotionEx 帧（player-car-only；packet_motion_ex 为全局单结构表）。"""
    where = "session_uid = ?" if session_uid is not None else "1=1"
    params = (session_uid,) if session_uid is not None else ()
    rows = store.query(
        "packet_motion_ex",
        where=where,
        params=params,
        order_by="overall_frame_identifier",
    )
    frames = []
    for row in rows:
        raw = row.get("m_wheelSlipRatio")
        if raw is None:
            continue
        slip = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(slip, (list, tuple)) or len(slip) < 4:
            continue
        frames.append(
            MotionExFrame(
                frame_id=row["overall_frame_identifier"],
                slip_ratios=tuple(float(x) for x in slip[:4]),
            )
        )
    return frames
