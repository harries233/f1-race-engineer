"""L4 确定性计算 —— 逐弯进阶指标（PHASE 13）：exit_traction（MotionEx 车轮滑移）。

`mid_stability`（转向抖动）与 `time_loss_phase`（参考圈对比）已在 `analysis.corner`；
本模块只处理需要 MotionEx（packet 13）的 `exit_traction`。

关键事实（官方 2026 Season Pack Spec）：
  - MotionEx 是 **player car ONLY** 数据（单结构，非 24 车），靠 header 的
    `m_playerCarIndex` 标识「正在驾驶的车」——exit_traction 只对玩家车有意义。
  - 车轮数组顺序固定为 RL, RR, FL, FR（Spec 明文）；F1 后轮驱动 → 驱动轮 = RL/RR
    （index 0, 1）。
  - MotionEx 无 m_lapDistance，只有 LapData 有；两者靠 header 全局单调帧号
    `m_overallFrameIdentifier` 时间对齐（口径同 corner.py / sector_segment.py）。

定义（PHASE 13 落定，确定性代理）：
  - exit_traction = 1 − mean(驱动轮 |slip ratio|) over 出口相样本，clamp [0,1]。
    slip ratio 越大（wheelspin）→ 牵引越差 → 分数越低；1 = 无滑移（满分）。
  - 出口相 = 该弯角内 lapDistance ≥ apex（最低速点）的 MotionEx 样本；不足 2 帧 → None。
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from analysis.corner import LapDistanceFrame

_DRIVEN_WHEELS = (0, 1)   # RL, RR（车轮数组顺序 RL,RR,FL,FR；F1 后驱）


@dataclass(frozen=True)
class MotionExFrame:
    """一帧 MotionEx 样本（来自 packet_motion_ex，player-car-only）。"""

    frame_id: int                          # m_overallFrameIdentifier
    slip_ratios: tuple[float, float, float, float]  # [RL, RR, FL, FR]，无量纲


@dataclass(frozen=True)
class MotionExSample:
    """一个对齐到 (圈号, lapDistance) 的 MotionEx 样本。"""

    lap_num: int
    lap_distance: float
    slip_ratios: tuple[float, float, float, float]


def align_motion_ex_to_lap_distance(
    motion_frames: list[MotionExFrame],
    lap_frames: list[LapDistanceFrame],
) -> list[MotionExSample]:
    """把 MotionEx 帧对齐到「最近的前一个（含等号）LapData 帧」的 (圈号, lapDistance)。

    丢弃无先行 LapData 帧的 MotionEx 帧（不编造归属）；口径同 corner.align_to_lap_distance。
    """
    m_frames = sorted(motion_frames, key=lambda f: f.frame_id)
    l_frames = sorted(lap_frames, key=lambda f: f.frame_id)

    samples: list[MotionExSample] = []
    lap_i = 0
    current = None
    for f in m_frames:
        while lap_i < len(l_frames) and l_frames[lap_i].frame_id <= f.frame_id:
            current = l_frames[lap_i]
            lap_i += 1
        if current is None:
            continue
        samples.append(
            MotionExSample(
                lap_num=current.lap_num,
                lap_distance=current.lap_distance,
                slip_ratios=f.slip_ratios,
            )
        )
    return samples


def exit_traction(
    samples: list[MotionExSample],
    apex_lap_distance: float,
) -> float | None:
    """出口相车轮滑移 → 牵引评分（0.0–1.0，1 = 无滑移）。

    出口相 = lapDistance ≥ apex 的样本（样本应已 assign 到该弯角区间内）；
    对每帧取驱动轮 |slip ratio| 的最大值，出口相内取均值，1 − 均值 得牵引分。
    出口相不足 2 帧 → None（NO DATA → NO FACT）。
    """
    exit_samples = [s for s in samples if s.lap_distance >= apex_lap_distance]
    if len(exit_samples) < 2:
        return None
    driven_slip = [
        max(abs(s.slip_ratios[i]) for i in _DRIVEN_WHEELS)
        for s in exit_samples
    ]
    return round(max(0.0, min(1.0, 1.0 - fmean(driven_slip))), 4)
