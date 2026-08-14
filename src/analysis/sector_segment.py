"""L4 确定性计算 —— 遥测速度流 → sector 边界切分（PHASE 9）。

把「属于哪个 sector」的边界判定从纯函数里解出来，落在这一层：速度样本
（CarTelemetry.m_speed）与 sector 标签（LapData.m_sector）是两种 packet，频率不同、
互不携带对方字段，只能靠 header 的全局单调帧号 `m_overallFrameIdentifier` 做时间对齐。

设计：
  - 速度样本归到「最近的前一个（含等号）LapData 帧」的 (圈号, sector)。
  - 这用游戏自报的 `m_sector`（GAME_DATA/RAW，最权威）做标签，而非用 Session 的
    sector 距离边界重建——避免插值误差。
  - 纯函数：输入两条已按帧号升序的帧序列，输出 {(lap_num, sector_index): [speeds]}。

诚实性：跨 packet 时间合并是近似（sector 切换瞬间可能错位 1 帧），故 get_sector 的
速度点置信度标 MEDIUM（非 HIGH），并在 notes 声明。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpeedFrame:
    """一帧速度样本（来自 packet_car_telemetry）。"""

    frame_id: int    # m_overallFrameIdentifier（全局单调）
    speed: float     # m_speed（km/h）


@dataclass(frozen=True)
class LapFrame:
    """一帧圈/sector 标签（来自 packet_lap_data）。"""

    frame_id: int    # m_overallFrameIdentifier
    lap_num: int     # m_currentLapNum
    sector: int      # m_sector（0/1/2）


def segment_speeds_by_sector(
    speed_frames: list[SpeedFrame],
    lap_frames: list[LapFrame],
) -> dict[tuple[int, int], list[float]]:
    """把速度样本按 (圈号, sector) 分组。

    每个速度样本归到「frame_id 不大于它的最近一个 LapFrame」的 (lap_num, sector)；
    若没有先行的 LapFrame（无法归属）则丢弃。返回键为 (lap_num, sector_index) 的
    dict，值为该分组内按帧序的速度序列（km/h）。
    """
    speeds = sorted(speed_frames, key=lambda f: f.frame_id)
    laps = sorted(lap_frames, key=lambda f: f.frame_id)

    grouped: dict[tuple[int, int], list[float]] = {}
    lap_i = 0
    current: LapFrame | None = None

    for speed in speeds:
        # 推进到「最后一个 frame_id <= speed.frame_id」的 LapFrame
        while lap_i < len(laps) and laps[lap_i].frame_id <= speed.frame_id:
            current = laps[lap_i]
            lap_i += 1
        if current is None:
            continue        # 无先行 sector 标签，丢弃（不编造归属）
        key = (current.lap_num, current.sector)
        grouped.setdefault(key, []).append(speed.speed)

    return grouped
