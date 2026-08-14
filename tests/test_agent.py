"""Unit tests：L5 RaceEngineer 调度骨架（PHASE 7）。"""

from agent.race_engineer import RaceEngineer
from ingest.receiver import TelemetryReceiver
from mock.factory import build_session_datagram
from store.schemas import SourceLevel
from store.structured_store import StructuredPacketStore


def _make_packet(datagram):
    receiver = TelemetryReceiver(port=12345)
    return receiver._to_packet(datagram, ("192.168.1.10", 51234))


def test_race_engineer_dispatches_tool(tmp_path):
    store = StructuredPacketStore(tmp_path / "t.sqlite3")
    store.save(_make_packet(build_session_datagram(weather=3)))

    engineer = RaceEngineer(store)
    assert "get_session" in engineer.tool_names()

    result = engineer.call("get_session")
    assert result.source_level == SourceLevel.RAW
    assert result.data["m_weather"] == 3
    store.close()


def test_race_engineer_exposes_schemas(tmp_path):
    store = StructuredPacketStore(tmp_path / "t.sqlite3")
    engineer = RaceEngineer(store)
    schemas = engineer.function_schemas()
    store.close()

    assert len(schemas) == 4
    assert all(s["type"] == "function" for s in schemas)
