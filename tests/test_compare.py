"""Unit tests：L4 compare（PHASE 8）—— compare_laps 确定性 delta 指标。"""

import pytest

from analysis.compare import compare_laps
from store.schemas import Confidence, LapRecord, SourceLevel


def _lap(lap_number, lap_time, s1, s2, s3, valid=True) -> LapRecord:
    return LapRecord(
        source_level=SourceLevel.DERIVED,
        source="calc:lap_metrics",
        timestamp="2026-08-14T00:00:00+00:00",
        unit="s",
        confidence=Confidence.HIGH,
        lap_number=lap_number,
        session_uid=1,
        lap_time=lap_time,
        sector1=s1,
        sector2=s2,
        sector3=s3,
        valid_flag=valid,
    )


def test_best_delta_negative_when_test_faster():
    baseline = [_lap(1, 95.0, 25.0, 30.0, 40.0), _lap(2, 96.0, 25.5, 30.5, 40.0)]
    test = [_lap(3, 94.0, 24.5, 29.5, 40.0)]
    result = compare_laps(baseline, test)
    assert result.best_delta == pytest.approx(-1.0)  # 94.0 - 95.0
    assert result.baseline_n == 2
    assert result.test_n == 1


def test_invalid_laps_skipped_and_counted():
    baseline = [_lap(1, 95.0, 25, 30, 40), _lap(2, 90.0, 20, 20, 20, valid=False)]
    test = [_lap(3, 94.0, 25, 30, 40)]
    result = compare_laps(baseline, test)
    assert result.baseline_n == 1
    assert result.baseline_invalid_skipped == 1
    assert result.baseline_best == pytest.approx(95.0)  # 90.0 无效被排除


def test_sector_deltas_use_best_per_side():
    baseline = [_lap(1, 95.0, 25.0, 30.0, 40.0)]
    test = [_lap(3, 94.0, 24.0, 31.0, 40.0)]
    result = compare_laps(baseline, test)
    assert result.sector1_delta == pytest.approx(-1.0)
    assert result.sector2_delta == pytest.approx(1.0)
    assert result.sector3_delta == pytest.approx(0.0)


def test_empty_side_yields_none_and_notes():
    result = compare_laps([], [_lap(3, 94.0, 24, 30, 40)])
    assert result.baseline_n == 0
    assert result.best_delta is None
    assert any("BASELINE" in n for n in result.notes)


def test_as_dict_keys_stable():
    baseline = [_lap(1, 95.0, 25, 30, 40)]
    test = [_lap(2, 94.0, 24.5, 29.5, 40)]
    d = compare_laps(baseline, test).as_dict()
    assert set(d) == {
        "baseline_n", "test_n", "baseline_invalid_skipped", "test_invalid_skipped",
        "baseline_best_s", "test_best_s", "best_delta_s", "mean_delta_s",
        "median_delta_s", "sector1_delta_s", "sector2_delta_s", "sector3_delta_s",
        "notes",
    }
