"""Unit tests：跨帧顺序校验（session_changed / frame 回退 / 重复帧 / sessionTime 回退）。"""

from mock.factory import build_datagram
from protocol.f1_25_2026.header import parse_header
from protocol.f1_25_2026.validate import build_validator
from store.schemas import PacketValidationStatus


def _reports(frames):
    validator = build_validator()
    return [
        validator.validate(datagram, parse_header(datagram)) for datagram in frames
    ]


def test_first_frame_no_sequence_issues():
    reports = _reports(
        [build_datagram(6, session_uid=100, frame_identifier=10, session_time=1.0)]
    )
    assert reports[0].status is PacketValidationStatus.VALID
    assert reports[0].issues == ()


def test_session_change_reports_info_and_resets():
    frames = [
        build_datagram(6, session_uid=100, frame_identifier=10, session_time=1.0),
        # 新会话：frame/time 归零，不因归零而误报回归
        build_datagram(6, session_uid=200, frame_identifier=0, session_time=0.0),
    ]
    reports = _reports(frames)
    codes = [i.code for i in reports[1].issues]
    assert "session_changed" in codes
    assert "frame_identifier_regression" not in codes
    assert "session_time_regression" not in codes
    assert reports[1].status is PacketValidationStatus.VALID  # INFO 不翻 status


def test_frame_identifier_regression_warns():
    frames = [
        build_datagram(6, session_uid=100, frame_identifier=10, session_time=1.0),
        build_datagram(6, session_uid=100, frame_identifier=5, session_time=1.5),
    ]
    reports = _reports(frames)
    codes = [i.code for i in reports[1].issues]
    assert "frame_identifier_regression" in codes
    assert reports[1].status is PacketValidationStatus.VALID


def test_duplicate_frame_warns():
    frames = [
        build_datagram(6, session_uid=100, frame_identifier=10, session_time=1.0),
        build_datagram(6, session_uid=100, frame_identifier=10, session_time=1.0),
    ]
    reports = _reports(frames)
    codes = [i.code for i in reports[1].issues]
    assert "duplicate_frame" in codes
    assert "frame_identifier_regression" not in codes  # 相等 → 重复，非回退
    assert reports[1].status is PacketValidationStatus.VALID


def test_session_time_regression_warns():
    frames = [
        build_datagram(6, session_uid=100, frame_identifier=10, session_time=5.0),
        build_datagram(6, session_uid=100, frame_identifier=11, session_time=3.0),
    ]
    reports = _reports(frames)
    codes = [i.code for i in reports[1].issues]
    assert "session_time_regression" in codes
    assert reports[1].status is PacketValidationStatus.VALID
