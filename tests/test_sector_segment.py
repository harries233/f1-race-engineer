"""Unit tests：L4 sector 速度流切分（PHASE 9）—— segment_speeds_by_sector。"""

from analysis.sector_segment import LapFrame, SpeedFrame, segment_speeds_by_sector


def test_groups_speeds_by_nearest_preceding_lap_frame():
    speeds = [
        SpeedFrame(11, 200.0), SpeedFrame(12, 90.0), SpeedFrame(13, 150.0),
        SpeedFrame(21, 150.0), SpeedFrame(22, 80.0), SpeedFrame(23, 170.0),
        SpeedFrame(31, 170.0), SpeedFrame(32, 100.0), SpeedFrame(33, 200.0),
    ]
    laps = [
        LapFrame(10, 1, 0),
        LapFrame(20, 1, 1),
        LapFrame(30, 1, 2),
    ]
    grouped = segment_speeds_by_sector(speeds, laps)
    assert grouped == {
        (1, 0): [200.0, 90.0, 150.0],
        (1, 1): [150.0, 80.0, 170.0],
        (1, 2): [170.0, 100.0, 200.0],
    }


def test_drops_speed_with_no_preceding_lap_frame():
    speeds = [SpeedFrame(5, 100.0), SpeedFrame(15, 120.0)]
    laps = [LapFrame(10, 1, 0)]
    grouped = segment_speeds_by_sector(speeds, laps)
    assert grouped == {(1, 0): [120.0]}  # 帧号 5 早于首个 lap 帧，被丢弃


def test_sorts_input_before_grouping():
    speeds = [SpeedFrame(12, 90.0), SpeedFrame(11, 200.0)]
    laps = [LapFrame(20, 2, 0), LapFrame(10, 1, 0)]
    grouped = segment_speeds_by_sector(speeds, laps)
    assert grouped == {(1, 0): [200.0, 90.0]}


def test_switch_to_next_lap():
    speeds = [SpeedFrame(11, 100.0), SpeedFrame(21, 200.0)]
    laps = [LapFrame(10, 1, 2), LapFrame(20, 2, 0)]
    grouped = segment_speeds_by_sector(speeds, laps)
    assert grouped == {(1, 2): [100.0], (2, 0): [200.0]}


def test_empty_speeds_returns_empty():
    assert segment_speeds_by_sector([], [LapFrame(10, 1, 0)]) == {}
