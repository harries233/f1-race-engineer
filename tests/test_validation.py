"""Unit tests：基础 Packet Validation（packetFormat/packetId/packetVersion/size/sessionUID/frame id）。"""

import pytest

from mock.factory import build_datagram, build_header_bytes
from protocol.f1_25_2026.header import HEADER_SIZE, parse_header
from protocol.f1_25_2026.parser import parse_packet
from store.schemas import PacketValidationStatus


def _status_of(datagram: bytes) -> PacketValidationStatus:
    return parse_packet(datagram).validation.status


def test_valid_packet_passes():
    datagram = build_datagram(6)  # Car Telemetry, 1448 bytes
    assert _status_of(datagram) is PacketValidationStatus.VALID


def test_short_datagram_failed():
    datagram = build_datagram(6, total_size=10)  # < 29
    assert len(datagram) < HEADER_SIZE
    result = parse_packet(datagram)
    assert result.validation.status is PacketValidationStatus.VALIDATION_FAILED
    assert result.header is None


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
    datagram = build_datagram(6, total_size=1000)
    result = parse_packet(datagram)
    assert result.validation.status is PacketValidationStatus.VALIDATION_FAILED
    # 记录 packet_id / expected_size / actual_size / difference
    joined = " ".join(result.validation.issues)
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
