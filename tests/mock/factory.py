"""MOCK_DATA —— 仅用于单元测试，禁止进入生产链路（物理隔离在 tests/mock/）。

提供合成 F1 25: 2026 Season Pack UDP datagram 的构造器。
"""

from __future__ import annotations

import struct

from protocol.f1_25_2026.header import HEADER_FORMAT, HEADER_SIZE
from protocol.f1_25_2026.packets import get_packet_definition
from protocol.f1_25_2026.structs import (
    CAR_TELEMETRY_FMT,
    LAP_DATA_FMT,
    LAP_HISTORY_FMT,
    MAX_LAP_HISTORY,
    MAX_TYRE_STINTS,
    TYRE_STINT_HISTORY_FMT,
)

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


# ---------------------------------------------------------------------------
# 真实 payload 构造器（PHASE 4）：用 struct.pack 造合法字段值供解析/校验/分析测试。
# ---------------------------------------------------------------------------

def _per_car_size(fmt: str) -> int:
    """标准 little-endian packed 结构体尺寸（强制 '<' 前缀）。"""
    return struct.calcsize("<" + fmt.lstrip("<"))


def build_car_telemetry_datagram(
    *,
    speed: int = 250,
    throttle: float = 0.8,
    steer: float = 0.0,
    brake: float = 0.0,
    clutch: int = 100,
    gear: int = 4,
    car_index: int = 0,
    **header_overrides,
) -> bytes:
    """Car Telemetry（packet 6）：把玩家车的前 6 个字段（speed..gear）写入真实值。

    字段序 `<HfffBb` = speed, throttle, steer, brake, clutch, gear，位于 per-car 结构体
    起始处连续 16 字节。其余字段零填充。
    """
    data = bytearray(build_datagram(6, **header_overrides))
    off = HEADER_SIZE + car_index * _per_car_size(CAR_TELEMETRY_FMT)
    struct.pack_into("<HfffBb", data, off, speed, throttle, steer, brake, clutch, gear)
    return bytes(data)


def build_event_datagram(
    code: str,
    details: bytes | None = None,
    **header_overrides,
) -> bytes:
    """Event（packet 3）：4 字节 eventStringCode + 12 字节 EventDataDetails union。"""
    details = (details if details is not None else b"\x00" * 12).ljust(12, b"\x00")[:12]
    code_bytes = code.encode("ascii")
    if len(code_bytes) != 4:
        raise ValueError("event code must be exactly 4 ascii chars")
    header = build_header_bytes(packet_id=3, **header_overrides)
    return header + code_bytes + details[:12]


def build_lap_data_datagram(
    *,
    car_index: int = 0,
    current_lap_num: int = 1,
    sector: int = 0,
    lap_distance: float = 0.0,
    current_lap_time_ms: int = 0,
    **header_overrides,
) -> bytes:
    """Lap Data（packet 2）：写入某车 currentLapNum / sector / lapDistance / currentLapTime。

    其余字段零填充；用 LAP_DATA_FMT 完整打包，避免手算偏移。
    """
    # 字段序见 structs.py LAP_DATA_FMT：II + HBHBHBHB + fff + B*15 + HHB + fB
    b15 = [0] * 15
    b15[1] = current_lap_num          # 15 个 uint8 中第 2 个 = m_currentLapNum
    b15[4] = sector                   # 第 5 个 = m_sector
    vals = (
        0, current_lap_time_ms,       # lastLapTimeInMS, currentLapTimeInMS
        0, 0, 0, 0, 0, 0, 0, 0,       # sector1/2 + deltaInFront + deltaLeader (HBHBHBHB)
        lap_distance, 0.0, 0.0,       # lapDistance, totalDistance, safetyCarDelta
        *b15,
        0, 0, 0,                      # pitLaneTimeInLaneInMS, pitStopTimerInMS, pitStopShouldServePen
        0.0, 0,                       # speedTrapFastestSpeed, speedTrapFastestLap
    )
    data = bytearray(build_datagram(2, **header_overrides))
    off = HEADER_SIZE + car_index * _per_car_size(LAP_DATA_FMT)
    struct.pack_into("<" + LAP_DATA_FMT, data, off, *vals)
    return bytes(data)


def build_session_history_datagram(
    *,
    lap_entries: list[tuple] | None = None,
    num_laps: int = 0,
    car_idx: int = 0,
    **header_overrides,
) -> bytes:
    """Session History（packet 11）：写入 N 条完赛圈明细（LAP_HISTORY_FMT 顺序）。

    lap_entries 元素为 8 元组，顺序：
      (lapTimeInMS, s1ms, s1min, s2ms, s2min, s3ms, s3min, lapValidBitFlags)
    """
    lap_entries = lap_entries or []
    payload = struct.pack("<BBBBBBB", car_idx, num_laps, 0, 0, 0, 0, 0)
    entry_size = _per_car_size(LAP_HISTORY_FMT)
    for i in range(MAX_LAP_HISTORY):
        if i < len(lap_entries):
            payload += struct.pack("<" + LAP_HISTORY_FMT, *lap_entries[i])
        else:
            payload += b"\x00" * entry_size
    payload += b"\x00" * (MAX_TYRE_STINTS * _per_car_size(TYRE_STINT_HISTORY_FMT))
    return build_header_bytes(packet_id=11, **header_overrides) + payload


def build_session_datagram(*, weather: int = 0, **header_overrides) -> bytes:
    """Session（packet 1）：把首个 payload 字段 weather（uint8）写入真实值。"""
    data = bytearray(build_datagram(1, **header_overrides))
    struct.pack_into("<B", data, HEADER_SIZE, weather)
    return bytes(data)
