"""Unit tests：PHASE 13 逐弯进阶指标 —— mid_stability / time_loss_phase / exit_traction。"""

import pytest

from analysis.corner import CornerMetrics, CornerSample, corner_metrics, phase_time_loss
from analysis.corner_advanced import (
    MotionExFrame,
    MotionExSample,
    align_motion_ex_to_lap_distance,
    exit_traction,
)
from analysis.corner import LapDistanceFrame
from ingest.receiver import TelemetryReceiver
from mock.factory import (
    build_car_telemetry_datagram,
    build_lap_data_datagram,
    build_motion_ex_datagram,
    build_session_datagram,
)
from store.structured_store import StructuredPacketStore
from tools import build_registry
from track import CornerDefinition, Track, register


def _cs(lap_distance, speed, steer=0.0):
    return CornerSample(
        lap_num=1, lap_distance=lap_distance, speed=speed,
        throttle=0.0, steer=steer, brake=0.0, gear=4,
    )


def _m(entry, mid, exit_):
    return CornerMetrics(
        entry_speed=entry, min_speed=mid, exit_speed=exit_,
        max_brake=0.0, max_steer=0.0, apex_throttle=0.0, exit_throttle=0.0,
        exit_gear=1, braking_point=None, brake_release=None, mid_stability=None,
    )


# ---------------------------------------------------------------------------
# mid_stability（中段转向抖动）
# ---------------------------------------------------------------------------

def test_mid_stability_constant_steer_is_one():
    samples = [_cs(float(i * 10), 100.0, steer=0.3) for i in range(9)]
    assert corner_metrics(samples).mid_stability == 1.0


def test_mid_stability_jitter_below_one():
    steers = [0.1] * 9
    steers[3:6] = [0.5, -0.3, 0.4]  # 中段 1/3 抖动
    samples = [_cs(float(i * 10), 100.0, steer=steers[i]) for i in range(9)]
    m = corner_metrics(samples)
    assert m.mid_stability is not None
    assert 0.0 < m.mid_stability < 1.0


def test_mid_stability_insufficient_samples_none():
    samples = [_cs(float(i * 10), 100.0) for i in range(3)]
    assert corner_metrics(samples).mid_stability is None


# ---------------------------------------------------------------------------
# time_loss_phase（参考圈对比）
# ---------------------------------------------------------------------------

def test_phase_time_loss_entry():
    assert phase_time_loss(_m(190, 90, 180), _m(210, 95, 182)) == "ENTRY"


def test_phase_time_loss_mid():
    assert phase_time_loss(_m(200, 80, 180), _m(205, 95, 183)) == "MID"


def test_phase_time_loss_exit():
    assert phase_time_loss(_m(200, 90, 170), _m(205, 95, 190)) == "EXIT"


def test_phase_time_loss_none_when_not_slower():
    assert phase_time_loss(_m(210, 100, 190), _m(200, 95, 185)) is None


# ---------------------------------------------------------------------------
# exit_traction（MotionEx 车轮滑移）
# ---------------------------------------------------------------------------

def _ms(lap_distance, slip):
    return MotionExSample(lap_num=1, lap_distance=lap_distance, slip_ratios=slip)


def test_exit_traction_driven_wheel_mean():
    samples = [
        _ms(50.0, (0.2, 0.3, 0.9, 0.9)),   # 出口前，排除
        _ms(80.0, (0.2, 0.3, 0.9, 0.9)),   # 驱动轮 max=0.3
        _ms(90.0, (0.4, 0.1, 0.9, 0.9)),   # 驱动轮 max=0.4
    ]
    assert exit_traction(samples, 60.0) == pytest.approx(1.0 - 0.35)


def test_exit_traction_ignores_front_wheels():
    samples = [_ms(80.0, (0.0, 0.0, 0.9, 0.9)), _ms(90.0, (0.0, 0.0, 0.8, 0.8))]
    assert exit_traction(samples, 60.0) == pytest.approx(1.0)


def test_exit_traction_insufficient_samples_none():
    assert exit_traction([_ms(80.0, (0.2, 0.3, 0.0, 0.0))], 60.0) is None


def test_align_motion_ex_to_lap_distance():
    frames = [
        MotionExFrame(11, (0.1, 0.2, 0.3, 0.4)),
        MotionExFrame(21, (0.5, 0.6, 0.7, 0.8)),
    ]
    laps = [LapDistanceFrame(10, 1, 50.0), LapDistanceFrame(20, 2, 10.0)]
    out = align_motion_ex_to_lap_distance(frames, laps)
    assert [(s.lap_num, s.lap_distance) for s in out] == [(1, 50.0), (2, 10.0)]


# ---------------------------------------------------------------------------
# Tool 集成：get_corner 三项字段
# ---------------------------------------------------------------------------

def _track():
    return Track(
        track_id="t", name="test", track_length_m=300.0,
        corners=[
            CornerDefinition(corner_number=1, name="c1", lap_distance_start=0.0, lap_distance_end=100.0),
            CornerDefinition(corner_number=2, name="c2", lap_distance_start=100.0, lap_distance_end=200.0),
            CornerDefinition(corner_number=3, name="c3", lap_distance_start=200.0, lap_distance_end=300.0),
        ],
    )


def _make_packet(datagram):
    receiver = TelemetryReceiver(port=12345)
    return receiver._to_packet(datagram, ("192.168.1.10", 51234))


def _fill_corner1_lap(store, lap_num, base_frame, speeds, steers):
    """corner 1（0–100m）铺 9 个样本：lap_distance 10..90，逐个打 lap + telemetry 帧。"""
    for i in range(9):
        d = (i + 1) * 10.0
        store.save(_make_packet(build_lap_data_datagram(
            car_index=0, current_lap_num=lap_num, lap_distance=d,
            overall_frame_identifier=base_frame + 2 * i)))
        store.save(_make_packet(build_car_telemetry_datagram(
            car_index=0, speed=speeds[i], steer=steers[i],
            overall_frame_identifier=base_frame + 2 * i + 1)))


def test_get_corner_advanced_fields_integration(tmp_path):
    store = StructuredPacketStore(tmp_path / "t.sqlite3")
    register(_track())

    lap1_speeds = [200, 180, 160, 140, 120, 130, 150, 170, 190]  # apex=120 @ index4
    lap2_speeds = [210, 190, 170, 150, 130, 145, 165, 185, 205]  # 更快，exit 更快 → ref
    steers = [0.1] * 9
    steers[3:6] = [0.5, -0.3, 0.4]  # 中段抖动 → mid_stability < 1

    _fill_corner1_lap(store, 1, 0, lap1_speeds, steers)
    _fill_corner1_lap(store, 2, 100, lap2_speeds, steers)

    # MotionEx（player-car-only）：lap1 出口 lap_distance 70/80，slip ratio 驱动轮滑移
    store.save(_make_packet(build_motion_ex_datagram(
        slip_ratios=(0.2, 0.3, 0.0, 0.0), overall_frame_identifier=13)))
    store.save(_make_packet(build_motion_ex_datagram(
        slip_ratios=(0.4, 0.1, 0.0, 0.0), overall_frame_identifier=15)))

    result = build_registry(store).call("get_corner", car_index=0, track_id="t")
    store.close()

    assert result.source_level.value == "DERIVED"
    recs = {(r["lap_number"], r["corner_number"]): r for r in result.data}
    c1_lap1 = recs[(1, 1)]
    c1_lap2 = recs[(2, 1)]

    # mid_stability：中段抖动 → 0 < x < 1
    assert 0.0 < c1_lap1["mid_stability"] < 1.0
    # time_loss_phase：lap1 vs 参考圈(lap2) 出口速度损失最大 → EXIT；参考圈自身 None
    assert c1_lap1["time_loss_phase"] == "EXIT"
    assert c1_lap2["time_loss_phase"] is None
    # exit_traction：MotionEx 驱动轮 slip 均值 0.35 → 0.65
    assert c1_lap1["exit_traction"] == pytest.approx(0.65)
    assert c1_lap2["exit_traction"] is None  # lap2 无 MotionEx 覆盖


def test_get_corner_resolves_track_from_session(tmp_path):
    store = StructuredPacketStore(tmp_path / "t.sqlite3")
    store.save(_make_packet(build_session_datagram(track_id=2, overall_frame_identifier=1)))
    # shanghai corner 1 遥测（track_id 缺省，由 m_trackId=2 解析）
    for i in range(3):
        d = (i + 1) * 10.0
        store.save(_make_packet(build_lap_data_datagram(
            car_index=0, current_lap_num=1, lap_distance=d, overall_frame_identifier=2 + 2 * i)))
        store.save(_make_packet(build_car_telemetry_datagram(
            car_index=0, speed=100 + i * 10, overall_frame_identifier=3 + 2 * i)))

    result = build_registry(store).call("get_corner", car_index=0, lap_number=1)
    store.close()

    assert result.data
    assert all(r["track_id"] == "shanghai" for r in result.data)
    assert any("m_trackId=2" in n for n in result.notes)
