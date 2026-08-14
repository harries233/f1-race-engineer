"""Unit tests：Tool 层（PHASE 6）—— get_session / get_telemetry / get_lap / list_sessions。"""

import pytest

from ingest.receiver import TelemetryReceiver
from mock.factory import (
    build_car_telemetry_datagram,
    build_datagram,
    build_session_datagram,
    build_session_history_datagram,
)
from store.experiment_store import ExperimentStore
from store.schemas import SourceLevel, ValidationStatus
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
        "compare", "save_setup", "list_setups", "validate_setup",
    }
    for s in schemas:
        assert s["type"] == "function"
        assert s["function"]["parameters"]["type"] == "object"


# ---------------------------------------------------------------------------
# PHASE 8 新增 Tool：compare / save_setup / list_setups / validate_setup
# ---------------------------------------------------------------------------

def test_compare_tool(db_path):
    store = ExperimentStore(db_path)
    entries = [
        (95000, 123, 0, 500, 0, 377, 0, 0x01),  # lap1 95.0s
        (96000, 130, 0, 510, 0, 380, 0, 0x01),  # lap2 96.0s
        (94000, 120, 0, 490, 0, 370, 0, 0x01),  # lap3 94.0s
    ]
    _seed(store, [build_session_history_datagram(lap_entries=entries, num_laps=3)])
    result = build_registry(store).call(
        "compare", car_index=0, baseline_laps=[1, 2], test_laps=[3]
    )
    store.close()

    assert result.source_level == SourceLevel.DERIVED
    assert result.data["best_delta_s"] == pytest.approx(-1.0)  # 94.0 - 95.0
    assert result.data["baseline_n"] == 2
    assert result.data["test_n"] == 1


def test_save_setup_and_list_setups(db_path):
    store = ExperimentStore(db_path)
    registry = build_registry(store)
    registry.call(
        "save_setup",
        setup_version="v1", track_id="shanghai", label="baseline",
        params={"front_wing": 30, "rear_wing": 25},
    )
    result = registry.call("list_setups")
    store.close()

    assert result.source_level == SourceLevel.GAME_DATA
    assert len(result.data) == 1
    assert result.data[0]["setup_version"] == "v1"
    assert result.data[0]["params"]["front_wing"] == 30


def test_validate_setup_tool_persists_experiment(db_path):
    store = ExperimentStore(db_path)
    entries = [
        (95000, 123, 0, 500, 0, 377, 0, 0x01),  # lap1
        (96000, 130, 0, 510, 0, 380, 0, 0x01),  # lap2
        (97000, 135, 0, 515, 0, 385, 0, 0x01),  # lap3
        (94000, 120, 0, 490, 0, 370, 0, 0x01),  # lap4
        (94100, 121, 0, 491, 0, 371, 0, 0x01),  # lap5
        (94200, 122, 0, 492, 0, 372, 0, 0x01),  # lap6
    ]
    _seed(store, [build_session_history_datagram(lap_entries=entries, num_laps=6)])
    result = build_registry(store).call(
        "validate_setup",
        exp_id="exp1",
        hypothesis="lower wing is faster",
        setup_baseline_version="v1",
        setup_test_version="v2",
        baseline_laps=[1, 2, 3],
        test_laps=[4, 5, 6],
        car_index=0,
    )

    assert result.data["status"] == "VALIDATED"
    assert store.get_experiment("exp1").status is ValidationStatus.VALIDATED
    store.close()
