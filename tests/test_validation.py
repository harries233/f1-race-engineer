"""Unit tests：header 基础校验（8 项 ERROR + 2 项 WARN），经 validate 框架。"""

import pytest

from mock.factory import build_datagram, build_header_bytes
from protocol.f1_25_2026.header import HEADER_SIZE, parse_header
from protocol.f1_25_2026.validate import build_validator
from store.schemas import PacketValidationStatus


def _report(datagram: bytes):
    return build_validator().validate(datagram, parse_header(datagram))


def _status_of(datagram: bytes) -> PacketValidationStatus:
    return _report(datagram).status


def test_valid_packet_passes():
    datagram = build_datagram(6)  # Car Telemetry, 1448 bytes
    assert _status_of(datagram) is PacketValidationStatus.VALID


def test_short_datagram_failed():
    datagram = build_datagram(6, total_size=10)  # < 29
    report = _report(datagram)
    assert report.status is PacketValidationStatus.VALIDATION_FAILED
    assert any(i.code == "datagram_too_short" for i in report.issues)


def test_invalid_packet_format_failed():
    datagram = build_datagram(6, packet_format=2025)
    assert _status_of(datagram) is PacketValidationStatus.VALIDATION_FAILED


def test_invalid_packet_id_failed():
    datagram = build_datagram(99)
    assert _status_of(datagram) is PacketValidationStatus.VALIDATION_FAILED


def test_invalid_packet_version_failed():
    datagram = build_datagram(6, packet_version=2)
    assert _status_of(datagram) is PacketValidationStatus.VALIDATION_FAILED


def test_packet_size_mismatch_failed():
    # 期望 1448，实际给 1000
    report = _report(build_datagram(6, total_size=1000))
    assert report.status is PacketValidationStatus.VALIDATION_FAILED
    # 记录 packet_id / expected_size / actual_size / difference
    joined = " ".join(i.message for i in report.issues)
    assert "packet_id=6" in joined
    assert "expected_size=1448" in joined
    assert "actual_size=1000" in joined
    assert "difference=-448" in joined


def test_session_uid_zero_failed():
    datagram = build_datagram(6, session_uid=0)
    assert _status_of(datagram) is PacketValidationStatus.VALIDATION_FAILED


def test_frame_identifier_type():
    # frameIdentifier / overallFrameIdentifier 均为 uint32（0..2^32-1）
    header = parse_header(
        build_header_bytes(frame_identifier=0xFFFFFFFF, overall_frame_identifier=0)
    )
    assert header.m_frameIdentifier == 0xFFFFFFFF
    assert header.m_overallFrameIdentifier == 0


def test_player_car_index_out_of_range_warns():
    report = _report(build_datagram(6, player_car_index=99))
    assert report.status is PacketValidationStatus.VALID  # WARN 不翻 status
    assert any(i.code == "player_car_index_out_of_range" for i in report.issues)


def test_secondary_player_car_index_out_of_range_warns():
    report = _report(build_datagram(6, secondary_player_car_index=42))
    assert report.status is PacketValidationStatus.VALID
    assert any(i.code == "secondary_player_car_index_out_of_range" for i in report.issues)
