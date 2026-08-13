"""L4 确定性计算 —— 分段时间与关键速度点（PHASE 4）。

纯函数，产出 `SectorRecord`（DERIVED，带 5 字段数据信封）。

关键事实（官方 Spec）：
  - 分段时间的权威来源是 LapData / SessionHistory 的 `m_sectorNTime`（拆成整分钟 +
    毫秒两部分），速度字段则由一段 CarTelemetry 流聚合。
  - `sector_speed_metrics` 只做「一段速度序列 → entry/min/exit」的确定性归约；
    把 Telemetry 流切成「属于哪个 sector」的边界判定属 PHASE 8/9 的接收端聚合，
    本 phase 不在这里做，避免在纯函数里引入时序状态。
"""

from __future__ import annotations

from dataclasses import dataclass

from store.schemas import Confidence, SectorRecord, SourceLevel


@dataclass(frozen=True)
class SpeedMetrics:
    """一段分段的三个关键速度点（km/h）。"""

    entry_speed: float
    min_speed: float
    exit_speed: float


def sector_speed_metrics(speeds: list[float]) -> SpeedMetrics:
    """一段速度序列 → entry/min/exit 速度。

    entry = 首帧，min = 全段最小，exit = 末帧。空序列抛 ValueError（无数据不产出）。
    """
    if not speeds:
        raise ValueError("sector_speed_metrics requires at least one speed sample")
    return SpeedMetrics(
        entry_speed=float(speeds[0]),
        min_speed=float(min(speeds)),
        exit_speed=float(speeds[-1]),
    )


def build_sector_record(
    *,
    lap_number: int,
    sector_index: int,
    sector_time: float,
    speeds: list[float],
    received_at: str,
) -> SectorRecord:
    """组装一条 SectorRecord：分段时间（RAW）+ 速度点（DERIVED）。

    参数：
      lap_number：所属圈号。
      sector_index：0/1/2。
      sector_time：该分段时间（秒，来自 sector_time_seconds 换算）。
      speeds：该分段内的 CarTelemetry 速度采样（km/h）；空则速度点留 None。
      received_at：UTC ISO8601（信封 timestamp）。
    """
    metrics = sector_speed_metrics(speeds) if speeds else None
    return SectorRecord(
        source_level=SourceLevel.DERIVED,
        source="calc:sector_metrics",
        timestamp=received_at,
        unit="km/h",
        confidence=Confidence.HIGH,
        lap_number=lap_number,
        sector_index=sector_index,
        sector_time=sector_time,
        entry_speed=metrics.entry_speed if metrics else None,
        min_speed=metrics.min_speed if metrics else None,
        exit_speed=metrics.exit_speed if metrics else None,
    )
