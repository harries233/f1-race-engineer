"""Unit tests：官方 Packet Registry（17 个 packet，ID/名称/size/version/频率类型）。"""

import pytest

from protocol.base import FrequencyType
from protocol.f1_25_2026.packets import (
    MAX_PACKET_ID,
    MIN_PACKET_ID,
    PACKET_REGISTRY,
    get_packet_definition,
    is_valid_packet_id,
)

EXPECTED = {
    0: ("Motion", 1325, FrequencyType.CONFIGURED_BY_GAME),
    1: ("Session", 926, FrequencyType.FIXED_RATE),
    2: ("Lap Data", 1399, FrequencyType.CONFIGURED_BY_GAME),
    3: ("Event", 45, FrequencyType.EVENT_DRIVEN),
    4: ("Participants", 1470, FrequencyType.FIXED_RATE),
    5: ("Car Setups", 1233, FrequencyType.FIXED_RATE),
    6: ("Car Telemetry", 1448, FrequencyType.CONFIGURED_BY_GAME),
    7: ("Car Status", 1445, FrequencyType.CONFIGURED_BY_GAME),
    8: ("Final Classification", 1134, FrequencyType.EVENT_DRIVEN),
    9: ("Lobby Info", 1062, FrequencyType.FIXED_RATE),
    10: ("Car Damage", 1133, FrequencyType.UNVERIFIED),
    11: ("Session History", 1460, FrequencyType.FIXED_RATE),
    12: ("Tyre Sets", 231, FrequencyType.FIXED_RATE),
    13: ("Motion Ex", 273, FrequencyType.CONFIGURED_BY_GAME),
    14: ("Time Trial", 104, FrequencyType.FIXED_RATE),
    15: ("Lap Positions", 1231, FrequencyType.FIXED_RATE),
    16: ("Car Telemetry 2", 269, FrequencyType.CONFIGURED_BY_GAME),
}


def test_registry_has_exactly_17_packets():
    assert len(PACKET_REGISTRY) == 17


@pytest.mark.parametrize("packet_id", list(EXPECTED))
def test_registry_entry(packet_id):
    name, size, freq = EXPECTED[packet_id]
    definition = get_packet_definition(packet_id)
    assert definition is not None
    assert definition.packet_id == packet_id
    assert definition.packet_name == name
    assert definition.expected_size == size
    assert definition.packet_version == 1
    assert definition.frequency_type is freq


def test_packet_version_all_equal_one():
    assert all(d.packet_version == 1 for d in PACKET_REGISTRY.values())


def test_car_damage_frequency_unverified():
    assert get_packet_definition(10).frequency_type is FrequencyType.UNVERIFIED


def test_valid_packet_id_range():
    assert MIN_PACKET_ID == 0
    assert MAX_PACKET_ID == 16
    assert is_valid_packet_id(0)
    assert is_valid_packet_id(16)
    assert not is_valid_packet_id(-1)
    assert not is_valid_packet_id(17)
