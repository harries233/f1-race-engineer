"""Unit tests：Tool 层（PHASE 6）—— get_session / get_telemetry / get_lap / list_sessions。"""

import pytest

from ingest.receiver import TelemetryReceiver
from mock.factory import (
    build_car_telemetry_datagram,
    build_datagram,
    build_session_datagram,
    build_session_history_datagram,
)
from store.schemas import SourceLevel
from store.structured_store import StructuredPacketStore
from tools import build_registry

DEFAULT_SESSION_UID = 0x1122334455667788


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "telemetry.sqlite3"


def _make_packet(datagram):
    receiver = TelemetryReceiver(port=12345)  # 仅构造，不 bind
    return receiver._to_packet(datagram, ("192.168.1.10", 51234))


def _seed(store, datagrams):
    for dg in datagrams:
        store.save(_make_packet(dg))


def test_get_session_raw(db_path):
    store = StructuredPacketStore(db_path)
    _seed(store, [build_session_datagram(weather=2)])
    result = build_registry(store).call("get_session")
    store.close()

    assert result.source_level == SourceLevel.RAW
    assert result.data["m_weather"] == 2
    assert result.data["session_uid"] == DEFAULT_SESSION_UID


def test_get_session_no_data(db_path):
    store = StructuredPacketStore(db_path)
    result = build_registry(store).call("get_session")
    store.close()

    assert result.data is None
    assert result.notes


def test_get_telemetry_raw(db_path):
    store = StructuredPacketStore(db_path)
    _seed(store, [build_car_telemetry_datagram(speed=250, throttle=0.8, gear=4)])
    result = build_registry(store).call("get_telemetry", car_index=0)
    store.close()

    assert result.source_level == SourceLevel.RAW
    data = result.data
    assert data["m_speed"] == 250
    assert data["m_throttle"] == pytest.approx(0.8)  # float32 round-trip
    assert data["m_gear"] == 4
    assert data["m_brakesTemperature"] == [0, 0, 0, 0]  # 数组字段反序列化
    assert data["car_index"] == 0


def test_get_lap_derived(db_path):
    store = StructuredPacketStore(db_path)
    # 一圈：lapTime=95000ms, s1=123ms, s2=500ms, s3=377ms, valid(0x01)
    entries = [(95000, 123, 0, 500, 0, 377, 0, 0x01)]
    _seed(store, [build_session_history_datagram(lap_entries=entries, num_laps=1)])
    result = build_registry(store).call("get_lap", car_index=0)
    store.close()

    assert result.source_level == SourceLevel.DERIVED
    assert len(result.data) == 1
    lap = result.data[0]
    assert lap["lap_number"] == 1
    assert lap["lap_time"] == pytest.approx(95.0)
    assert lap["sector1"] == pytest.approx(0.123)
    assert lap["sector2"] == pytest.approx(0.5)
    assert lap["sector3"] == pytest.approx(0.377)
    assert lap["valid_flag"] is True
    assert lap["session_uid"] == DEFAULT_SESSION_UID


def test_get_lap_filtered_by_lap_number(db_path):
    store = StructuredPacketStore(db_path)
    entries = [(95000, 123, 0, 500, 0, 377, 0, 0x01), (94000, 100, 0, 400, 0, 300, 0, 0x01)]
    _seed(store, [build_session_history_datagram(lap_entries=entries, num_laps=2)])
    result = build_registry(store).call("get_lap", car_index=0, lap_number=2)
    store.close()

    assert len(result.data) == 1
    assert result.data[0]["lap_number"] == 2


def test_get_lap_no_data(db_path):
    store = StructuredPacketStore(db_path)
    result = build_registry(store).call("get_lap", car_index=0)
    store.close()

    assert result.data == []
    assert result.notes


def test_list_sessions(db_path):
    store = StructuredPacketStore(db_path)
    _seed(store, [
        build_datagram(6, session_uid=1),
        build_datagram(6, session_uid=2, frame_identifier=9999),
    ])
    result = build_registry(store).call("list_sessions")
    store.close()

    assert {s["session_uid"] for s in result.data} == {1, 2}
    assert all(s["packet_count"] == 1 for s in result.data)


def test_unknown_tool_raises(db_path):
    store = StructuredPacketStore(db_path)
    registry = build_registry(store)
    with pytest.raises(KeyError):
        registry.call("no_such_tool")
    store.close()


def test_function_schemas_shape(db_path):
    store = StructuredPacketStore(db_path)
    registry = build_registry(store)
    schemas = registry.function_schemas()
    store.close()

    assert {s["function"]["name"] for s in schemas} == {
        "get_session", "get_telemetry", "get_lap", "list_sessions",
    }
    for s in schemas:
        assert s["type"] == "function"
        assert s["function"]["parameters"]["type"] == "object"
