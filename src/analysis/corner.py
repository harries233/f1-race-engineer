"""L4 确定性计算 —— 逐弯指标（CornerRecord，PHASE 11）。

依赖独立赛道数据层（`track.Track`）提供「哪段 m_lapDistance 是几号弯」。UDP 遥测本身
不带弯角几何，故本模块只做「把一段 telemetry 样本归约成 entry/mid/exit 指标」的
确定性计算，几何来自 `track`。

关键事实：
  - CarTelemetry 没有 m_lapDistance，只有 LapData 有；两者靠 header 全局单调帧号
    `m_overallFrameIdentifier` 时间对齐（同 PHASE 9 sector 切分口径）。
  - 弯角指标全部 DERIVED；弯角边界为估算（HYPOTHESIS），故 CornerRecord 置信度 MEDIUM。
  - 需参考圈对比的字段（time_loss_phase）、需 MotionEx 车轮滑移的（exit_traction）、
    需稳定性定义的（mid_stability）本 phase 不产出，留 None（诚实声明缺数据）。

字段口径：
  - entry/mid/exit 速度：弯角区间内速度序列的首帧 / 最小 / 末帧。
  - entry_brake_pressure：区间内最大刹车输入（×100 → %）。
  - entry_braking_point / entry_brake_release：首个 / 最后一个刹车输入 > 阈值的
    lapDistance（米）。
  - mid_steering：区间内最大 |转向|；mid_throttle：最低速点（apex）的油门；
    exit_throttle_application：末帧油门；exit_gear：末帧挡位。
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass

from store.schemas import Confidence, CornerRecord, SourceLevel
from track import Track

_BRAKE_THRESHOLD = 0.05   # 判定「正在刹车」的最小刹车输入（m_brake，0.0–1.0）


@dataclass(frozen=True)
class TelemetryFrame:
    """一帧 CarTelemetry 样本（来自 packet_car_telemetry）。"""

    frame_id: int      # m_overallFrameIdentifier
    speed: float       # m_speed（km/h）
    throttle: float    # m_throttle（0.0–1.0）
    steer: float       # m_steer（-1.0–1.0）
    brake: float       # m_brake（0.0–1.0）
    gear: int          # m_gear（1–8，N=0，R=-1）


@dataclass(frozen=True)
class LapDistanceFrame:
    """一帧 LapData 的里程标签（来自 packet_lap_data）。"""

    frame_id: int          # m_overallFrameIdentifier
    lap_num: int           # m_currentLapNum
    lap_distance: float    # m_lapDistance（沿赛道里程，米）


@dataclass(frozen=True)
class CornerSample:
    """一个对齐到 (圈号, lapDistance) 的遥测样本。"""

    lap_num: int
    lap_distance: float
    speed: float
    throttle: float
    steer: float
    brake: float
    gear: int


@dataclass(frozen=True)
class CornerMetrics:
    """一个弯角区间内归约出的 entry/mid/exit 指标。"""

    entry_speed: float
    min_speed: float
    exit_speed: float
    max_brake: float             # 0.0–1.0
    max_steer: float             # 0.0–1.0（|m_steer| 峰值）
    apex_throttle: float         # 最低速点油门（0.0–1.0）
    exit_throttle: float         # 末帧油门（0.0–1.0）
    exit_gear: int
    braking_point: float | None  # m（lapDistance，首个刹车 > 阈值）
    brake_release: float | None  # m（lapDistance，最后一个刹车 > 阈值）


def align_to_lap_distance(
    telemetry_frames: list[TelemetryFrame],
    lap_frames: list[LapDistanceFrame],
) -> list[CornerSample]:
    """把 telemetry 帧对齐到「最近的前一个（含等号）LapData 帧」的 (圈号, lapDistance)。

    丢弃无先行 LapData 帧的 telemetry 帧（不编造归属）；口径同 sector_segment。
    """
    t_frames = sorted(telemetry_frames, key=lambda f: f.frame_id)
    l_frames = sorted(lap_frames, key=lambda f: f.frame_id)

    samples: list[CornerSample] = []
    lap_i = 0
    current: LapDistanceFrame | None = None
    for t in t_frames:
        while lap_i < len(l_frames) and l_frames[lap_i].frame_id <= t.frame_id:
            current = l_frames[lap_i]
            lap_i += 1
        if current is None:
            continue
        samples.append(
            CornerSample(
                lap_num=current.lap_num,
                lap_distance=current.lap_distance,
                speed=t.speed,
                throttle=t.throttle,
                steer=t.steer,
                brake=t.brake,
                gear=t.gear,
            )
        )
    return samples


def assign_corners(
    samples: list[CornerSample],
    track: Track,
) -> dict[int, list[CornerSample]]:
    """把样本按 lapDistance 落到弯角区间；间隙 / 超界样本丢弃。键 = corner_number。"""
    corners = sorted(track.corners, key=lambda c: c.lap_distance_start)
    starts = [c.lap_distance_start for c in corners]

    grouped: dict[int, list[CornerSample]] = {}
    for s in samples:
        i = bisect_right(starts, s.lap_distance) - 1
        if i < 0:
            continue
        c = corners[i]
        if s.lap_distance >= c.lap_distance_end:
            continue
        grouped.setdefault(c.corner_number, []).append(s)
    return grouped


def corner_metrics(samples: list[CornerSample]) -> CornerMetrics:
    """一个弯角区间的样本 → entry/mid/exit 指标（确定性归约）。

    空序列抛 ValueError（无数据不产出）。
    """
    if not samples:
        raise ValueError("corner_metrics requires at least one sample")

    ordered = sorted(samples, key=lambda s: s.lap_distance)
    entry = ordered[0]
    exit_ = ordered[-1]
    apex = min(ordered, key=lambda s: s.speed)
    braking = [s for s in ordered if s.brake > _BRAKE_THRESHOLD]

    return CornerMetrics(
        entry_speed=float(entry.speed),
        min_speed=float(apex.speed),
        exit_speed=float(exit_.speed),
        max_brake=float(max(s.brake for s in ordered)),
        max_steer=float(max(abs(s.steer) for s in ordered)),
        apex_throttle=float(apex.throttle),
        exit_throttle=float(exit_.throttle),
        exit_gear=int(exit_.gear),
        braking_point=braking[0].lap_distance if braking else None,
        brake_release=braking[-1].lap_distance if braking else None,
    )


def build_corner_record(
    *,
    track: Track,
    corner_number: int,
    samples: list[CornerSample],
    lap_number: int,
    received_at: str,
) -> CornerRecord:
    """组装一条 CornerRecord（DERIVED，置信度 MEDIUM——弯角边界为估算）。"""
    m = corner_metrics(samples)
    return CornerRecord(
        source_level=SourceLevel.DERIVED,
        source="calc:corner_metrics",
        timestamp=received_at,
        unit="km/h",
        confidence=Confidence.MEDIUM,
        track_id=track.track_id,
        corner_number=corner_number,
        entry_braking_point=m.braking_point,
        entry_brake_pressure=m.max_brake * 100.0,
        entry_brake_release=m.brake_release,
        entry_speed=m.entry_speed,
        mid_min_speed=m.min_speed,
        mid_steering=m.max_steer,
        mid_throttle=m.apex_throttle,
        mid_stability=None,              # 需稳定性定义 + 参考圈，本 phase 不产出
        exit_throttle_application=m.exit_throttle,
        exit_traction=None,              # 需 MotionEx 车轮滑移，跨 packet，本 phase 不产出
        exit_speed=m.exit_speed,
        exit_gear=m.exit_gear,
        time_loss_phase=None,            # 需参考圈对比，本 phase 不产出
    )
