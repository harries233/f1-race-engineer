"""Unit tests：payload 解析（17 结构体 round-trip + Event union + 失败兜底）。"""

import struct

import pytest

from mock.factory import (
    build_car_telemetry_datagram,
    build_datagram,
    build_event_datagram,
    build_session_history_datagram,
)
from protocol.f1_25_2026.header import HEADER_SIZE
from protocol.f1_25_2026.packets import PACKET_REGISTRY
from protocol.f1_25_2026.payload import (
    PacketCarDamageData,
    PacketCarSetupData,
    PacketCarStatusData,
    PacketCarTelemetry2Data,
    PacketCarTelemetryData,
    PacketEventData,
    PacketFinalClassificationData,
    PacketLapData,
    PacketLapPositionsData,
    PacketLobbyInfoData,
    PacketMotionData,
    PacketMotionExData,
    PacketParticipantsData,
    PacketSessionData,
    PacketSessionHistoryData,
    PacketTimeTrialData,
    PacketTyreSetsData,
    parse_payload,
)
from protocol.f1_25_2026.structs import PACKET_PAYLOAD_FMT


# packet_id → 期望顶层模型类（17 个全覆盖）
EXPECTED_CLASSES = {
    0: PacketMotionData,
    1: PacketSessionData,
    2: PacketLapData,
    3: PacketEventData,
    4: PacketParticipantsData,
    5: PacketCarSetupData,
    6: PacketCarTelemetryData,
    7: PacketCarStatusData,
    8: PacketFinalClassificationData,
    9: PacketLobbyInfoData,
    10: PacketCarDamageData,
    11: PacketSessionHistoryData,
    12: PacketTyreSetsData,
    13: PacketMotionExData,
    14: PacketTimeTrialData,
    15: PacketLapPositionsData,
    16: PacketCarTelemetry2Data,
}


@pytest.mark.parametrize("packet_id", range(17))
def test_every_packet_parses_to_expected_type(packet_id):
    datagram = build_datagram(packet_id)  # 零填充 payload，尺寸与 registry 对齐
    parsed = parse_payload(packet_id, datagram)
    assert parsed is not None, f"packet_id={packet_id} 应解析成功"
    assert isinstance(parsed, EXPECTED_CLASSES[packet_id])


def test_payload_size_matches_registry():
    """第二层兜底：每个格式串 calcsize == registry expected_size - 29（import 期已断言）。"""
    for packet_id, definition in PACKET_REGISTRY.items():
        fmt = PACKET_PAYLOAD_FMT[packet_id]
        expected_payload = definition.expected_size - HEADER_SIZE
        assert struct.calcsize(fmt) == expected_payload, (
            f"packet_id={packet_id} payload size mismatch"
        )


def test_car_telemetry_roundtrip():
    parsed = parse_payload(
        6, build_car_telemetry_datagram(speed=250, throttle=0.8, gear=4)
    )
    car = parsed.m_carTelemetryData[0]
    assert car.m_speed == 250
    assert car.m_throttle == pytest.approx(0.8)
    assert car.m_gear == 4
    # 数组字段仍按 list 聚合（4 元素）
    assert car.m_brakesTemperature == [0, 0, 0, 0]
    assert car.m_tyresPressure == [0.0, 0.0, 0.0, 0.0]


def test_session_history_roundtrip():
    entry = (92534, 25500, 0, 30500, 0, 36534, 0, 0x01)
    parsed = parse_payload(
        11, build_session_history_datagram(lap_entries=[entry], num_laps=1)
    )
    assert parsed.m_numLaps == 1
    lap = parsed.m_lapHistoryData[0]
    assert lap.m_lapTimeInMS == 92534
    assert lap.m_sector1TimeMSPart == 25500
    assert lap.m_sector2TimeMSPart == 30500
    assert lap.m_sector3TimeMSPart == 36534
    assert lap.m_lapValidBitFlags == 0x01
    # 未填充的圈为 0
    assert parsed.m_lapHistoryData[1].m_lapTimeInMS == 0


def test_event_union_ftlp():
    details = struct.pack("<Bf", 5, 92.5)
    parsed = parse_payload(3, build_event_datagram("FTLP", details))
    assert parsed.m_eventStringCode == "FTLP"
    assert parsed.m_eventDetails == {"vehicleIdx": 5, "lapTime": pytest.approx(92.5)}


def test_event_unknown_code_keeps_raw():
    parsed = parse_payload(3, build_event_datagram("XXXX"))
    assert parsed.m_eventStringCode == "XXXX"
    assert parsed.m_eventDetails == {}


def test_parse_payload_unknown_id_returns_none():
    assert parse_payload(99, build_datagram(99)) is None


def test_parse_payload_short_payload_returns_none():
    # packet 6 期望 1448，给 40 字节 → 长度不足 → None
    assert parse_payload(6, build_datagram(6, total_size=40)) is None
