"""Unit tests：header 解析（29 字节 / little-endian / packed / 12 字段）。"""

import struct

import pytest

from mock.factory import build_header_bytes
from protocol.f1_25_2026.header import (
    HEADER_FORMAT,
    HEADER_SIZE,
    PACKET_FORMAT,
    parse_header,
)
from store.schemas import PacketHeader


def test_header_size_is_29():
    assert HEADER_SIZE == 29
    assert struct.calcsize(HEADER_FORMAT) == 29


def test_header_format_is_little_endian_packed():
    # 小端：低位字节在前。packetFormat=2026 -> 0x07EA -> 字节序 EA 07
    raw = build_header_bytes(packet_format=2026)
    assert raw[0] == 0xEA
    assert raw[1] == 0x07


def test_parse_header_all_fields():
    header = parse_header(
        build_header_bytes(
            packet_format=2026,
            game_year=26,
            game_major=1,
            game_minor=1,
            packet_version=1,
            packet_id=6,
            session_uid=0x1122334455667788,
            session_time=123.456,
            frame_identifier=12345,
            overall_frame_identifier=54321,
            player_car_index=3,
            secondary_player_car_index=255,
        )
    )
    assert isinstance(header, PacketHeader)
    assert header.m_packetFormat == 2026
    assert header.m_gameYear == 26
    assert header.m_gameMajorVersion == 1
    assert header.m_gameMinorVersion == 1
    assert header.m_packetVersion == 1
    assert header.m_packetId == 6
    assert header.m_sessionUID == 0x1122334455667788
    assert header.m_sessionTime == pytest.approx(123.456)
    assert header.m_frameIdentifier == 12345
    assert header.m_overallFrameIdentifier == 54321
    assert header.m_playerCarIndex == 3
    assert header.m_secondaryPlayerCarIndex == 255


def test_packet_format_constant_is_2026():
    assert PACKET_FORMAT == 2026


def test_parse_header_short_datagram_returns_none():
    assert parse_header(b"\x00" * 28) is None
    assert parse_header(b"") is None


def test_game_year_read_from_data_not_hardcoded():
    # gameYear 必须来自真实数据：构造 game_year=99 也应原样读出，而非硬编码 26
    header = parse_header(build_header_bytes(game_year=99))
    assert header.m_gameYear == 99
