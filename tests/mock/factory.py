"""MOCK_DATA —— 仅用于单元测试，禁止进入生产链路（物理隔离在 tests/mock/）。

提供合成 F1 25: 2026 Season Pack UDP datagram 的构造器。
"""

from __future__ import annotations

import struct

from protocol.f1_25_2026.header import HEADER_FORMAT, HEADER_SIZE
from protocol.f1_25_2026.packets import get_packet_definition

# 默认 mock 值（全部合法，便于测试通过；测试可覆盖个别字段制造失败场景）
DEFAULT_PACKET_FORMAT = 2026
DEFAULT_GAME_YEAR = 25  # VERIFIED：真实 2026-format 数据 gameYear=25（.txt "e.g. 26" 是笔误）
DEFAULT_GAME_MAJOR = 1
DEFAULT_GAME_MINOR = 1
DEFAULT_PACKET_VERSION = 1
DEFAULT_SESSION_UID = 0x1122334455667788
DEFAULT_SESSION_TIME = 123.456
DEFAULT_FRAME_IDENTIFIER = 12345
DEFAULT_OVERALL_FRAME_IDENTIFIER = 54321
DEFAULT_PLAYER_CAR_INDEX = 0
DEFAULT_SECONDARY_PLAYER_CAR_INDEX = 255


def build_header_bytes(
    *,
    packet_format: int = DEFAULT_PACKET_FORMAT,
    game_year: int = DEFAULT_GAME_YEAR,
    game_major: int = DEFAULT_GAME_MAJOR,
    game_minor: int = DEFAULT_GAME_MINOR,
    packet_version: int = DEFAULT_PACKET_VERSION,
    packet_id: int = 0,
    session_uid: int = DEFAULT_SESSION_UID,
    session_time: float = DEFAULT_SESSION_TIME,
    frame_identifier: int = DEFAULT_FRAME_IDENTIFIER,
    overall_frame_identifier: int = DEFAULT_OVERALL_FRAME_IDENTIFIER,
    player_car_index: int = DEFAULT_PLAYER_CAR_INDEX,
    secondary_player_car_index: int = DEFAULT_SECONDARY_PLAYER_CAR_INDEX,
) -> bytes:
    """按官方顺序打包 29 字节 header（little-endian, packed）。"""
    return struct.pack(
        HEADER_FORMAT,
        packet_format,
        game_year,
        game_major,
        game_minor,
        packet_version,
        packet_id,
        session_uid,
        session_time,
        frame_identifier,
        overall_frame_identifier,
        player_car_index,
        secondary_player_car_index,
    )


def build_datagram(
    packet_id: int,
    *,
    packet_format: int = DEFAULT_PACKET_FORMAT,
    packet_version: int = DEFAULT_PACKET_VERSION,
    session_uid: int = DEFAULT_SESSION_UID,
    total_size: int | None = None,
    **header_overrides,
) -> bytes:
    """构造一帧完整 datagram：header + 零填充 payload。

    total_size 缺省时取官方 registry 的 expected_size（含 29 字节 header）。
    显式传 total_size 可制造 size 不匹配 / datagram < 29 的场景。
    """
    if total_size is None:
        definition = get_packet_definition(packet_id)
        total_size = definition.expected_size if definition is not None else HEADER_SIZE

    header = build_header_bytes(
        packet_id=packet_id,
        packet_format=packet_format,
        packet_version=packet_version,
        session_uid=session_uid,
        **header_overrides,
    )
    if total_size < HEADER_SIZE:
        return header[:total_size]  # 制造 datagram < 29 的场景
    return header + b"\x00" * (total_size - HEADER_SIZE)
