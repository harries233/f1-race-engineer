"""Unit tests：L4 确定性计算（圈速/分段时间/速度点）。"""

import pytest

from analysis.lap import (
    build_lap_record,
    lap_time_seconds,
    lap_valid_from_bitflags,
    sector_time_seconds,
)
from analysis.sector import build_sector_record, sector_speed_metrics
from protocol.f1_25_2026.payload import LapHistoryData
from store.schemas import Confidence, SourceLevel


def _lap_history(**overrides) -> LapHistoryData:
    d = dict(
        m_lapTimeInMS=92534, m_sector1TimeMSPart=25500, m_sector1TimeMinutesPart=0,
        m_sector2TimeMSPart=30500, m_sector2TimeMinutesPart=0,
        m_sector3TimeMSPart=36534, m_sector3TimeMinutesPart=0, m_lapValidBitFlags=0x01,
    )
    d.update(overrides)
    return LapHistoryData(**d)


def test_sector_time_seconds():
    assert sector_time_seconds(0, 25500) == pytest.approx(25.5)
    assert sector_time_seconds(1, 500) == pytest.approx(60.5)


def test_lap_time_seconds():
    assert lap_time_seconds(92534) == pytest.approx(92.534)


def test_lap_valid_from_bitflags():
    assert lap_valid_from_bitflags(0x01) is True
    assert lap_valid_from_bitflags(0x00) is False


def test_build_lap_record_envelope_and_values():
    record = build_lap_record(
        _lap_history(), lap_number=3, session_uid=42,
        received_at="2026-08-13T00:00:00+00:00", setup_version="v1",
    )
    # 5 字段信封
    assert record.source_level is SourceLevel.DERIVED
    assert record.source == "calc:lap_metrics"
    assert record.timestamp == "2026-08-13T00:00:00+00:00"
    assert record.unit == "s"
    assert record.confidence is Confidence.HIGH
    # 换算值
    assert record.lap_number == 3
    assert record.session_uid == 42
    assert record.lap_time == pytest.approx(92.534)
    assert record.sector1 == pytest.approx(25.5)
    assert record.sector2 == pytest.approx(30.5)
    assert record.sector3 == pytest.approx(36.534)
    assert record.valid_flag is True
    assert record.setup_version == "v1"


def test_build_lap_record_invalid_lap():
    record = build_lap_record(
        _lap_history(m_lapValidBitFlags=0x00), lap_number=1, session_uid=1,
        received_at="x",
    )
    assert record.valid_flag is False


def test_sector_speed_metrics():
    metrics = sector_speed_metrics([250.0, 200.0, 90.0, 180.0])
    assert metrics.entry_speed == 250.0
    assert metrics.min_speed == 90.0
    assert metrics.exit_speed == 180.0


def test_sector_speed_metrics_empty_raises():
    with pytest.raises(ValueError):
        sector_speed_metrics([])


def test_build_sector_record_envelope_and_values():
    record = build_sector_record(
        lap_number=2, sector_index=1, sector_time=30.5,
        speeds=[250.0, 200.0, 90.0, 180.0], received_at="2026-08-13T00:00:00+00:00",
    )
    assert record.source_level is SourceLevel.DERIVED
    assert record.source == "calc:sector_metrics"
    assert record.unit == "km/h"
    assert record.confidence is Confidence.HIGH
    assert record.lap_number == 2
    assert record.sector_index == 1
    assert record.sector_time == pytest.approx(30.5)
    assert record.entry_speed == 250.0
    assert record.min_speed == 90.0
    assert record.exit_speed == 180.0


def test_build_sector_record_no_speeds_leaves_none():
    record = build_sector_record(
        lap_number=2, sector_index=0, sector_time=25.5, speeds=[],
        received_at="x",
    )
    assert record.entry_speed is None
    assert record.min_speed is None
    assert record.exit_speed is None
