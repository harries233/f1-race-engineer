"""L4 分析层（确定性计算）—— lap / sector 指标。

产出 `LapRecord` / `SectorRecord`（DERIVED，带 5 字段数据信封）。纯函数、无模型。
"""

from analysis.lap import (
    build_lap_record,
    lap_time_seconds,
    lap_valid_from_bitflags,
    sector_time_seconds,
)
from analysis.sector import (
    SpeedMetrics,
    build_sector_record,
    sector_speed_metrics,
)
from analysis.corner import (
    CornerMetrics,
    align_to_lap_distance,
    assign_corners,
    build_corner_record,
    corner_metrics,
)

__all__ = [
    "CornerMetrics",
    "SpeedMetrics",
    "align_to_lap_distance",
    "assign_corners",
    "build_corner_record",
    "build_lap_record",
    "build_sector_record",
    "corner_metrics",
    "lap_time_seconds",
    "lap_valid_from_bitflags",
    "sector_speed_metrics",
    "sector_time_seconds",
]
