"""Unit tests：m_trackId → track_id 映射表（PHASE 13，官方 Track ID 附录）。"""

from track import TRACK_IDS, TRACK_NAMES, track_id_for, track_name_for


def test_shanghai_is_track_id_2():
    assert track_id_for(2) == "shanghai"
    assert track_name_for(2) == "Shanghai"


def test_track_id_for_known_ids():
    assert track_id_for(0) == "melbourne"
    assert track_id_for(13) == "suzuka"
    assert track_id_for(42) == "madrid"


def test_track_id_for_unknown_returns_none():
    # -1 = unknown（Spec 明文）；以及不在附录里的 id
    assert track_id_for(-1) is None
    assert track_id_for(1) is None
    assert track_id_for(8) is None
    assert track_id_for(255) is None


def test_track_name_for_unknown_returns_none():
    assert track_name_for(-1) is None
    assert track_name_for(99) is None


def test_mapping_consistent_slug_and_name():
    assert len(TRACK_IDS) == len(TRACK_NAMES) == 28
    assert set(TRACK_IDS) == set(TRACK_NAMES)
    # 每个 slug 都应是合法 registry 键风格（小写 + 下划线）
    for slug in TRACK_IDS.values():
        assert slug == slug.lower()
        assert " " not in slug
