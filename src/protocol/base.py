"""Protocol 分层基础定义（协议无关）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FrequencyType(str, Enum):
    """Packet 发送频率类别（不把每个 packet 都写成固定 Hz）。"""

    CONFIGURED_BY_GAME = "CONFIGURED_BY_GAME"   # 由游戏内菜单指定发送频率
    FIXED_RATE = "FIXED_RATE"                   # 固定频率
    EVENT_DRIVEN = "EVENT_DRIVEN"               # 事件驱动（如结束时一次）
    UNVERIFIED = "UNVERIFIED"                   # 官方 Spec 内部矛盾，未验证


@dataclass(frozen=True)
class PacketDefinition:
    """单个 Packet 的注册信息（来自官方 Spec）。"""

    packet_id: int
    packet_name: str
    packet_version: int
    expected_size: int          # 完整 datagram 长度（含 29 字节 header）
    frequency_type: FrequencyType
    frequency_note: str = ""    # 补充说明，如 "2/s"、"菜单指定"、"20/s 轮询车辆"
