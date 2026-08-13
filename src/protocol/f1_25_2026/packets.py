"""F1 25: 2026 Season Pack 官方 Packet Registry。

17 个 packet 的 packet_id / packet_name / packet_version / expected_size / frequency_type。
expected_size 为完整 datagram 长度（含 29 字节 header），取自官方 Spec 的字节注释。
频率区分 CONFIGURED_BY_GAME / FIXED_RATE / EVENT_DRIVEN，不全部写成固定 Hz。
"""

from __future__ import annotations

from protocol.base import FrequencyType, PacketDefinition

PACKET_REGISTRY: dict[int, PacketDefinition] = {
    0: PacketDefinition(0, "Motion", 1, 1325, FrequencyType.CONFIGURED_BY_GAME, "菜单指定"),
    1: PacketDefinition(1, "Session", 1, 926, FrequencyType.FIXED_RATE, "2/s"),
    2: PacketDefinition(2, "Lap Data", 1, 1399, FrequencyType.CONFIGURED_BY_GAME, "菜单指定"),
    3: PacketDefinition(3, "Event", 1, 45, FrequencyType.EVENT_DRIVEN, "事件时"),
    4: PacketDefinition(4, "Participants", 1, 1470, FrequencyType.FIXED_RATE, "每 5s"),
    5: PacketDefinition(5, "Car Setups", 1, 1233, FrequencyType.FIXED_RATE, "2/s"),
    6: PacketDefinition(6, "Car Telemetry", 1, 1448, FrequencyType.CONFIGURED_BY_GAME, "菜单指定"),
    7: PacketDefinition(7, "Car Status", 1, 1445, FrequencyType.CONFIGURED_BY_GAME, "菜单指定"),
    8: PacketDefinition(8, "Final Classification", 1, 1134, FrequencyType.EVENT_DRIVEN, "结束时一次"),
    9: PacketDefinition(9, "Lobby Info", 1, 1062, FrequencyType.FIXED_RATE, "大厅 ~2/s"),
    10: PacketDefinition(10, "Car Damage", 1, 1133, FrequencyType.UNVERIFIED, "正文 10/s vs FAQ 2/s 矛盾"),
    11: PacketDefinition(11, "Session History", 1, 1460, FrequencyType.FIXED_RATE, "20/s 轮询车辆"),
    12: PacketDefinition(12, "Tyre Sets", 1, 231, FrequencyType.FIXED_RATE, "20/s 轮询车辆"),
    13: PacketDefinition(13, "Motion Ex", 1, 273, FrequencyType.CONFIGURED_BY_GAME, "菜单指定"),
    14: PacketDefinition(14, "Time Trial", 1, 104, FrequencyType.FIXED_RATE, "1/s"),
    15: PacketDefinition(15, "Lap Positions", 1, 1231, FrequencyType.FIXED_RATE, "1/s"),
    16: PacketDefinition(16, "Car Telemetry 2", 1, 269, FrequencyType.CONFIGURED_BY_GAME, "菜单指定"),
}

MIN_PACKET_ID = 0
MAX_PACKET_ID = 16


def get_packet_definition(packet_id: int) -> PacketDefinition | None:
    """按 packet_id 取注册信息；未知 id 返回 None。"""
    return PACKET_REGISTRY.get(packet_id)


def is_valid_packet_id(packet_id: int) -> bool:
    """packetId 是否在官方范围 [0, 16] 内。"""
    return MIN_PACKET_ID <= packet_id <= MAX_PACKET_ID
