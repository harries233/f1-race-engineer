"""Unit tests：TelemetryReceiver（source_address / validation_status / payload 保留 / UDP_PORT_NOT_CONFIGURED）。"""

import pytest

from ingest.receiver import (
    DEFAULT_HOST,
    TelemetryReceiver,
    UDPPortNotConfiguredError,
)
from mock.factory import build_datagram
from store.schemas import PacketValidationStatus


def test_port_not_configured_raises():
    with pytest.raises(UDPPortNotConfiguredError) as excinfo:
        TelemetryReceiver(port=None)
    assert "UDP_PORT_NOT_CONFIGURED" in str(excinfo.value)


def test_default_host_preserved():
    assert DEFAULT_HOST == "0.0.0.0"


def test_to_packet_preserves_payload_and_source():
    receiver = TelemetryReceiver(port=12345)  # 仅构造，不 bind
    datagram = build_datagram(6)
    packet = receiver._to_packet(datagram, ("192.168.1.10", 51234))

    assert packet.payload == datagram
    assert packet.source_address == "192.168.1.10:51234"
    assert packet.received_at  # 非空
    assert packet.validation_status is PacketValidationStatus.VALID
    assert packet.validation_issues == []      # 有效帧无 issue 明细
    assert packet.header is not None
    assert packet.header.m_packetId == 6


def test_to_packet_failed_keeps_raw_datagram():
    receiver = TelemetryReceiver(port=12345)
    datagram = build_datagram(6, packet_format=2025)
    packet = receiver._to_packet(datagram, ("10.0.0.1", 9999))

    assert packet.payload == datagram
    assert packet.validation_status is PacketValidationStatus.VALIDATION_FAILED
    assert any(i.code == "packet_format_mismatch" for i in packet.validation_issues)
