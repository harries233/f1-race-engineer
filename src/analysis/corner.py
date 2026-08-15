"""L4 确定性计算 —— 逐弯指标（CornerRecord，PHASE 11）。

依赖独立赛道数据层（`track.Track`）提供「哪段 m_lapDistance 是几号弯」。UDP 遥测本身
不带弯角几何，故本模块只做「把一段 telemetry 样本归约成 entry/mid/exit 指标」的
确定性计算，几何来自 `track`。

关键事实：
  - CarTelemetry 没有 m_lapDistance，只有 LapData 有；两者靠 header 全局单调帧号
    `m_overallFrameIdentifier` 时间对齐（同 PHASE 9 sector 切分口径）。
  - 弯角指标全部 DERIVED；弯角边界为估算（HYPOTHESIS），故 CornerRecord 置信度 MEDIUM。
  - PHASE 13 起：mid_stability 由中段转向抖动推导（corner_metrics 内）；time_loss_phase
    （参考圈对比）与 exit_traction（MotionEx 车轮滑移）依赖跨圈/跨 packet 数据，
    由调用方经 phase_time_loss / corner_advanced.exit_traction 算好后传入。

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
from statistics import pstdev

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
    mid_stability: float | None  # 0.0–1.0，1=最稳（中段转向抖动越少越稳）


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
        mid_stability=_mid_stability(ordered),
    )


def _mid_stability(ordered: list[CornerSample]) -> float | None:
    """中段转向抖动 → 稳定性（0.0–1.0，1=最稳）。

    定义：取按 lapDistance 升序的中段 1/3 样本，`1 − pstdev(steer)`。
      - 转向越平稳（中段 steering 抖动越小），pstdev 越小 → 稳定性越接近 1。
      - 样本不足 3 个 → None（NO DATA → NO FACT，不编造稳定性）。
    这是「中段稳定性」的一个确定性代理定义（PHASE 13 落定），非物理量纲。
    """
    mid = _middle_third(ordered)
    if len(mid) < 3:
        return None
    std = pstdev(s.steer for s in mid)
    return round(max(0.0, min(1.0, 1.0 - std)), 4)


def _middle_third(ordered: list[CornerSample]) -> list[CornerSample]:
    """按样本数取中段 1/3（lapDistance 升序的中央窗口）。不足 3 个返回空。"""
    n = len(ordered)
    if n < 3:
        return []
    third = max(1, n // 3)
    start = (n - third) // 2
    return ordered[start:start + third]


_PHASES = ("ENTRY", "MID", "EXIT")


def phase_time_loss(cur: CornerMetrics, ref: CornerMetrics) -> str | None:
    """参考圈对比 → 本弯角在哪一相（ENTRY|MID|EXIT）损失最多时间（PHASE 13）。

    以 entry_speed / min_speed / exit_speed 三个速度点近似三相的速度表现：
      deficit[ENTRY] = ref.entry_speed − cur.entry_speed，余类推（km/h）。
    取 deficit 最大的相；若三相均不慢于参考（deficit ≤ 0，本圈即/优于参考），
    返回 None（无时间损失，NO DATA → NO FACT 不编造）。
    """
    deficits = (
        (ref.entry_speed - cur.entry_speed),
        (ref.min_speed - cur.min_speed),
        (ref.exit_speed - cur.exit_speed),
    )
    worst = max(deficits)
    if worst <= 0:
        return None
    return _PHASES[deficits.index(worst)]


def build_corner_record(
    *,
    track: Track,
    corner_number: int,
    samples: list[CornerSample],
    lap_number: int,
    received_at: str,
    time_loss_phase: str | None = None,
    exit_traction: float | None = None,
) -> CornerRecord:
    """组装一条 CornerRecord（DERIVED，置信度 MEDIUM——弯角边界为估算）。

    `mid_stability` 由样本内转向抖动确定性推导；`time_loss_phase`（参考圈对比）与
    `exit_traction`（MotionEx 车轮滑移）依赖跨圈 / 跨 packet 数据，由调用方算好后传入。
    """
    m = corner_metrics(samples)
    return CornerRecord(
        source_level=SourceLevel.DERIVED,
        source="calc:corner_metrics",
        timestamp=received_at,
        unit="km/h",
        confidence=Confidence.MEDIUM,
        track_id=track.track_id,
        lap_number=lap_number,
        corner_number=corner_number,
        entry_braking_point=m.braking_point,
        entry_brake_pressure=m.max_brake * 100.0,
        entry_brake_release=m.brake_release,
        entry_speed=m.entry_speed,
        mid_min_speed=m.min_speed,
        mid_steering=m.max_steer,
        mid_throttle=m.apex_throttle,
        mid_stability=m.mid_stability,
        exit_throttle_application=m.exit_throttle,
        exit_traction=exit_traction,
        exit_speed=m.exit_speed,
        exit_gear=m.exit_gear,
        time_loss_phase=time_loss_phase,
    )
