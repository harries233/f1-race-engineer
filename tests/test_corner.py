"""Unit tests：L4 逐弯指标（PHASE 11）—— 赛道数据层 + analysis.corner + get_corner。"""

import pytest

from analysis.corner import (
    CornerSample,
    LapDistanceFrame,
    TelemetryFrame,
    align_to_lap_distance,
    assign_corners,
    build_corner_record,
    corner_metrics,
)
from ingest.receiver import TelemetryReceiver
from mock.factory import build_car_telemetry_datagram, build_lap_data_datagram
from store.schemas import Confidence, SourceLevel
from store.structured_store import StructuredPacketStore
from tools import build_registry
from track import CornerDefinition, Track, get_track, list_tracks, register


def _track() -> Track:
    """3 弯测试赛道：全长 300m，每弯 100m，用于确定性断言。"""
    return Track(
        track_id="t",
        name="test",
        track_length_m=300.0,
        corners=[
            CornerDefinition(corner_number=1, name="c1", lap_distance_start=0.0, lap_distance_end=100.0),
            CornerDefinition(corner_number=2, name="c2", lap_distance_start=100.0, lap_distance_end=200.0),
            CornerDefinition(corner_number=3, name="c3", lap_distance_start=200.0, lap_distance_end=300.0),
        ],
    )


def _sample(lap_distance, speed, throttle=0.0, steer=0.0, brake=0.0, gear=4):
    return CornerSample(
        lap_num=1,
        lap_distance=lap_distance,
        speed=speed,
        throttle=throttle,
        steer=steer,
        brake=brake,
        gear=gear,
    )


# ---------------------------------------------------------------------------
# 纯函数：对齐 / 分段 / 归约 / 组装
# ---------------------------------------------------------------------------

def test_align_to_lap_distance_nearest_preceding():
    tele = [
        TelemetryFrame(11, 200.0, 0.0, 0.0, 0.0, 6),
        TelemetryFrame(21, 180.0, 1.0, 0.0, 0.0, 6),
    ]
    laps = [LapDistanceFrame(10, 1, 50.0), LapDistanceFrame(20, 2, 10.0)]
    samples = align_to_lap_distance(tele, laps)
    assert [(s.lap_num, s.lap_distance) for s in samples] == [(1, 50.0), (2, 10.0)]


def test_align_to_lap_distance_drops_no_preceding():
    tele = [TelemetryFrame(5, 100.0, 0.0, 0.0, 0.0, 1), TelemetryFrame(15, 120.0, 0.0, 0.0, 0.0, 2)]
    laps = [LapDistanceFrame(10, 1, 0.0)]
    samples = align_to_lap_distance(tele, laps)
    assert [(s.lap_num, s.lap_distance) for s in samples] == [(1, 0.0)]


def test_assign_corners_by_distance():
    track = _track()
    samples = [_sample(50.0, 200.0), _sample(150.0, 120.0), _sample(250.0, 180.0)]
    grouped = assign_corners(samples, track)
    assert set(grouped) == {1, 2, 3}
    assert grouped[1][0].speed == 200.0
    assert grouped[2][0].speed == 120.0
    assert grouped[3][0].speed == 180.0


def test_assign_corners_drops_gap_sample():
    track = Track(
        track_id="g",
        name="gap",
        track_length_m=300.0,
        corners=[
            CornerDefinition(corner_number=1, name="c1", lap_distance_start=0.0, lap_distance_end=100.0),
            CornerDefinition(corner_number=2, name="c2", lap_distance_start=200.0, lap_distance_end=300.0),
        ],
    )
    grouped = assign_corners([_sample(150.0, 100.0)], track)  # 落在 100–200 间隙
    assert grouped == {}


def test_corner_metrics_entry_mid_exit():
    samples = [
        _sample(100.0, 200.0, throttle=0.0, steer=0.0, brake=0.0, gear=6),
        _sample(110.0, 150.0, throttle=0.0, steer=0.3, brake=0.8, gear=5),
        _sample(120.0, 80.0, throttle=0.1, steer=0.5, brake=0.4, gear=4),
        _sample(130.0, 120.0, throttle=0.6, steer=0.1, brake=0.0, gear=5),
        _sample(140.0, 180.0, throttle=1.0, steer=0.0, brake=0.0, gear=6),
    ]
    m = corner_metrics(samples)
    assert m.entry_speed == 200.0
    assert m.min_speed == 80.0
    assert m.exit_speed == 180.0
    assert m.max_brake == pytest.approx(0.8)
    assert m.max_steer == pytest.approx(0.5)
    assert m.apex_throttle == pytest.approx(0.1)   # 最低速点油门
    assert m.exit_throttle == pytest.approx(1.0)
    assert m.exit_gear == 6
    assert m.braking_point == 110.0               # 首个 brake>0.05 的 lapDistance
    assert m.brake_release == 120.0               # 最后一个 brake>0.05 的 lapDistance


def test_corner_metrics_no_braking():
    m = corner_metrics([_sample(50.0, 150.0, brake=0.0), _sample(60.0, 160.0, brake=0.0)])
    assert m.braking_point is None
    assert m.brake_release is None


def test_corner_metrics_empty_raises():
    with pytest.raises(ValueError):
        corner_metrics([])


def test_build_corner_record_envelope():
    track = _track()
    samples = [
        _sample(50.0, 200.0, brake=0.0, gear=6),
        _sample(60.0, 90.0, brake=0.8, gear=4),
    ]
    r = build_corner_record(
        track=track, corner_number=1, samples=samples, lap_number=1,
        received_at="2026-08-14T00:00:00Z",
    )
    assert r.source_level == SourceLevel.DERIVED
    assert r.confidence == Confidence.MEDIUM
    assert r.track_id == "t"
    assert r.corner_number == 1
    assert r.entry_speed == 200.0
    assert r.mid_min_speed == 90.0
    assert r.entry_brake_pressure == pytest.approx(80.0)
    assert r.time_loss_phase is None
    assert r.mid_stability is None
    assert r.exit_traction is None


# ---------------------------------------------------------------------------
# 赛道数据层
# ---------------------------------------------------------------------------

def test_track_seed_shanghai_registered():
    shanghai = get_track("shanghai")
    assert shanghai is not None
    assert shanghai.track_length_m == pytest.approx(5451.0)
    assert len(shanghai.corners) == 16
    assert [c.corner_number for c in shanghai.corners] == list(range(1, 17))
    assert any(t.track_id == "shanghai" for t in list_tracks())


# ---------------------------------------------------------------------------
# Tool 集成：get_corner
# ---------------------------------------------------------------------------

def _make_packet(datagram):
    receiver = TelemetryReceiver(port=12345)
    return receiver._to_packet(datagram, ("192.168.1.10", 51234))


def test_get_corner_tool_integration(tmp_path):
    store = StructuredPacketStore(tmp_path / "t.sqlite3")
    register(_track())  # 注册 3 弯测试赛道，走 track_id 解析路径
    # 圈里程标签（frame 10/20/30）+ 遥测帧（frame 11/12/21/31），按帧号对齐
    store.save(_make_packet(build_lap_data_datagram(
        car_index=0, current_lap_num=1, lap_distance=50.0, overall_frame_identifier=10)))
    store.save(_make_packet(build_car_telemetry_datagram(
        car_index=0, speed=200, brake=0.0, gear=6, overall_frame_identifier=11)))
    store.save(_make_packet(build_car_telemetry_datagram(
        car_index=0, speed=90, brake=0.8, gear=4, overall_frame_identifier=12)))
    store.save(_make_packet(build_lap_data_datagram(
        car_index=0, current_lap_num=1, lap_distance=150.0, overall_frame_identifier=20)))
    store.save(_make_packet(build_car_telemetry_datagram(
        car_index=0, speed=120, brake=0.0, gear=5, overall_frame_identifier=21)))
    store.save(_make_packet(build_lap_data_datagram(
        car_index=0, current_lap_num=1, lap_distance=250.0, overall_frame_identifier=30)))
    store.save(_make_packet(build_car_telemetry_datagram(
        car_index=0, speed=180, brake=0.0, gear=6, overall_frame_identifier=31)))

    result = build_registry(store).call("get_corner", car_index=0, lap_number=1, track_id="t")
    store.close()

    assert result.source_level == SourceLevel.DERIVED
    assert result.confidence == Confidence.MEDIUM
    records = {r["corner_number"]: r for r in result.data}
    assert set(records) == {1, 2, 3}
    assert records[1]["entry_speed"] == 200.0
    assert records[1]["mid_min_speed"] == 90.0
    assert records[1]["entry_brake_pressure"] == pytest.approx(80.0)
    assert records[2]["entry_speed"] == 120.0
    assert records[3]["entry_speed"] == 180.0


def test_get_corner_unknown_track(tmp_path):
    store = StructuredPacketStore(tmp_path / "t.sqlite3")
    result = build_registry(store).call("get_corner", car_index=0, track_id="nope")
    store.close()
    assert result.data == []
    assert any("未知赛道" in n for n in result.notes)


def test_get_corner_no_data(tmp_path):
    store = StructuredPacketStore(tmp_path / "t.sqlite3")
    result = build_registry(store).call("get_corner", car_index=0)
    store.close()
    assert result.data == []
    assert result.notes
