"""F1 25: 2026 Season Pack 的 29 字节 header 解析。

官方 Spec 明文：Little Endian、packed、无 padding。字段顺序/类型（struct PacketHeader）：

    uint16  m_packetFormat             // 2026
    uint8   m_gameYear                 // 25（VERIFIED：真实数据 + .pdf；.txt 注释 "e.g. 26" 是笔误）
    uint8   m_gameMajorVersion
    uint8   m_gameMinorVersion
    uint8   m_packetVersion
    uint8   m_packetId
    uint64  m_sessionUID
    float   m_sessionTime
    uint32  m_frameIdentifier
    uint32  m_overallFrameIdentifier
    uint8   m_playerCarIndex
    uint8   m_secondaryPlayerCarIndex  // 255 = 无第二玩家
"""

from __future__ import annotations

import struct
from typing import Optional

from store.schemas import PacketHeader

PACKET_FORMAT = 2026
HEADER_FORMAT = "<HBBBBBQfIIBB"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# 编译期保证：header 必须正好 29 字节（官方 Spec 明文）。
assert HEADER_SIZE == 29, f"Header size mismatch: {HEADER_SIZE} != 29"


def parse_header(data: bytes) -> Optional[PacketHeader]:
    """解析 29 字节 header（little-endian, packed）。

    datagram 长度 < 29 时返回 None（对应 VALIDATION_FAILED，不得尝试解析）。
    """
    if len(data) < HEADER_SIZE:
        return None
    (
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
    ) = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
    return PacketHeader(
        m_packetFormat=packet_format,
        m_gameYear=game_year,
        m_gameMajorVersion=game_major,
        m_gameMinorVersion=game_minor,
        m_packetVersion=packet_version,
        m_packetId=packet_id,
        m_sessionUID=session_uid,
        m_sessionTime=session_time,
        m_frameIdentifier=frame_identifier,
        m_overallFrameIdentifier=overall_frame_identifier,
        m_playerCarIndex=player_car_index,
        m_secondaryPlayerCarIndex=secondary_player_car_index,
    )
