"""L4 确定性计算 —— 圈速对比（PHASE 8）。

纯 Python 函数，不靠模型。把两组 `LapRecord`（BASELINE / TEST）归约成可追溯的
delta 指标，供 A-B 实验（`analysis/experiment.py`）与 `compare` Tool 使用。

约定：
  - delta = test − baseline（秒）。**负值 = test 更快（改进）**。
  - 只对比 `valid_flag is True` 的有效圈；无效圈被跳过并计数，不混入指标。
  - 无有效圈 → 相应 delta 为 None（NO DATA → NO FACT，不编造数字）。
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from store.schemas import LapRecord


def _valid_laps(laps: list[LapRecord]) -> list[LapRecord]:
    """只取有效圈（valid_flag is True）；None/False 视为无效，不参与对比。"""
    return [lap for lap in laps if lap.valid_flag is True]


def _best(laps: list[LapRecord], attr: str) -> float | None:
    """有效圈中该字段（秒）的最小值 = 最快；无有效圈返回 None。"""
    values = [getattr(lap, attr) for lap in laps if getattr(lap, attr) is not None]
    return min(values) if values else None


def _mean(laps: list[LapRecord], attr: str) -> float | None:
    values = [getattr(lap, attr) for lap in laps if getattr(lap, attr) is not None]
    return statistics.fmean(values) if values else None


def _median(laps: list[LapRecord], attr: str) -> float | None:
    values = [getattr(lap, attr) for lap in laps if getattr(lap, attr) is not None]
    return statistics.median(values) if values else None


def _delta(base: float | None, test: float | None) -> float | None:
    """test − base；任一侧为 None → None。"""
    if base is None or test is None:
        return None
    return test - base


@dataclass(frozen=True)
class CompareResult:
    """两组圈速的确定性对比结果（delta 单位：秒，负 = test 更快）。"""

    baseline_n: int
    test_n: int
    baseline_invalid_skipped: int
    test_invalid_skipped: int
    baseline_best: float | None
    test_best: float | None
    best_delta: float | None
    mean_delta: float | None
    median_delta: float | None
    sector1_delta: float | None
    sector2_delta: float | None
    sector3_delta: float | None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict:
        """序列化成可落库 / 可进 ToolResult.data 的稳定 dict（键名即契约）。"""
        return {
            "baseline_n": self.baseline_n,
            "test_n": self.test_n,
            "baseline_invalid_skipped": self.baseline_invalid_skipped,
            "test_invalid_skipped": self.test_invalid_skipped,
            "baseline_best_s": self.baseline_best,
            "test_best_s": self.test_best,
            "best_delta_s": self.best_delta,
            "mean_delta_s": self.mean_delta,
            "median_delta_s": self.median_delta,
            "sector1_delta_s": self.sector1_delta,
            "sector2_delta_s": self.sector2_delta,
            "sector3_delta_s": self.sector3_delta,
            "notes": list(self.notes),
        }


def compare_laps(baseline: list[LapRecord], test: list[LapRecord]) -> CompareResult:
    """BASELINE vs TEST 圈速对比。

    只统计有效圈；无效圈跳过并计数。best = 组内最快圈；mean/median = 组内平均/中位。
    sectorN_delta = 两侧 sectorN 最快分段时间之差。
    """
    base_valid = _valid_laps(baseline)
    test_valid = _valid_laps(test)

    notes = []
    if not base_valid:
        notes.append("BASELINE 无有效圈，无法计算 delta")
    if not test_valid:
        notes.append("TEST 无有效圈，无法计算 delta")
    if len(baseline) != len(base_valid) or len(test) != len(test_valid):
        notes.append(
            f"已跳过无效圈：baseline {len(baseline) - len(base_valid)} / "
            f"test {len(test) - len(test_valid)}"
        )

    return CompareResult(
        baseline_n=len(base_valid),
        test_n=len(test_valid),
        baseline_invalid_skipped=len(baseline) - len(base_valid),
        test_invalid_skipped=len(test) - len(test_valid),
        baseline_best=_best(base_valid, "lap_time"),
        test_best=_best(test_valid, "lap_time"),
        best_delta=_delta(_best(base_valid, "lap_time"), _best(test_valid, "lap_time")),
        mean_delta=_delta(_mean(base_valid, "lap_time"), _mean(test_valid, "lap_time")),
        median_delta=_delta(_median(base_valid, "lap_time"), _median(test_valid, "lap_time")),
        sector1_delta=_delta(_best(base_valid, "sector1"), _best(test_valid, "sector1")),
        sector2_delta=_delta(_best(base_valid, "sector2"), _best(test_valid, "sector2")),
        sector3_delta=_delta(_best(base_valid, "sector3"), _best(test_valid, "sector3")),
        notes=tuple(notes),
    )
