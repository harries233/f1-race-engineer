"""Unit tests：HTTP/WS 服务层（PHASE 14）—— build_event / Service.ingest / REST / WS / ask。"""

import pytest
from fastapi.testclient import TestClient

from agent.claude import ClaudeRaceEngineer
from ingest.receiver import TelemetryReceiver
from mock.factory import (
    build_car_telemetry_datagram,
    build_datagram,
    build_session_datagram,
    build_session_history_datagram,
)
from server.app import create_app
from server.events import build_event
from server.service import Service
from store.experiment_store import ExperimentStore

DEFAULT_SESSION_UID = 0x1122334455667788


def _make_packet(datagram):
    return TelemetryReceiver(port=12345)._to_packet(datagram, ("192.168.1.10", 51234))


# ---------------------------------------------------------------------------
# build_event：从 RawPacket.structured 提取实时事件
# ---------------------------------------------------------------------------

def test_build_event_car_telemetry_player_car():
    packet = _make_packet(build_car_telemetry_datagram(speed=250, throttle=0.8, gear=4))
    event = build_event(packet)

    assert event is not None
    assert event["type"] == "telemetry"
    assert event["packet"] == "car_telemetry"
    assert event["car_index"] == 0
    assert event["source_level"] == "RAW"
    assert event["session_uid"] == DEFAULT_SESSION_UID
    assert event["data"]["m_speed"] == 250
    assert event["data"]["m_gear"] == 4


def test_build_event_session_global():
    packet = _make_packet(build_session_datagram(weather=2, track_id=2))
    event = build_event(packet)

    assert event["packet"] == "session"
    assert event["data"]["m_weather"] == 2
    assert event["data"]["m_trackId"] == 2


def test_build_event_ignores_non_dashboard_packet():
    packet = _make_packet(build_datagram(0))  # motion：car 包但不在广播清单
    assert build_event(packet) is None


# ---------------------------------------------------------------------------
# Service.ingest：落库 + 广播（用 spy 捕获，避开异步）
# ---------------------------------------------------------------------------

def test_ingest_saves_and_publishes(tmp_path):
    store = ExperimentStore(tmp_path / "t.sqlite3")
    events = []
    service = Service(store, on_event=events.append)

    raw_id = service.ingest(_make_packet(build_car_telemetry_datagram(speed=250)))

    assert raw_id == 1
    assert store.count() == 1
    assert len(events) == 1
    assert events[0]["packet"] == "car_telemetry"
    store.close()


# ---------------------------------------------------------------------------
# REST 端点：薄封装 Tool 层，保留 5 字段诚实信封
# ---------------------------------------------------------------------------

def _seed_session_telemetry(store):
    store.save(_make_packet(build_session_datagram(weather=2, track_id=2)))
    store.save(_make_packet(build_car_telemetry_datagram(speed=250, throttle=0.8, gear=4)))


def test_health(tmp_path):
    store = ExperimentStore(tmp_path / "t.sqlite3")
    _seed_session_telemetry(store)
    with TestClient(create_app(Service(store))) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["packet_count"] == 2
    store.close()


def test_sessions_envelope(tmp_path):
    store = ExperimentStore(tmp_path / "t.sqlite3")
    _seed_session_telemetry(store)
    with TestClient(create_app(Service(store))) as client:
        body = client.get("/api/sessions").json()
    store.close()

    assert body["source_level"] == "RAW"
    assert body["confidence"] == "HIGH"
    assert len(body["data"]) == 1
    assert body["data"][0]["session_uid"] == DEFAULT_SESSION_UID


def test_session_resolves_track(tmp_path):
    store = ExperimentStore(tmp_path / "t.sqlite3")
    _seed_session_telemetry(store)
    with TestClient(create_app(Service(store))) as client:
        body = client.get("/api/session").json()
    store.close()

    assert body["data"]["m_weather"] == 2
    assert body["data"]["track_id"] == "shanghai"  # m_trackId=2 → 官方附录 Shanghai
    assert body["data"]["track_name"] == "Shanghai"


def test_telemetry_envelope(tmp_path):
    store = ExperimentStore(tmp_path / "t.sqlite3")
    _seed_session_telemetry(store)
    with TestClient(create_app(Service(store))) as client:
        body = client.get("/api/telemetry", params={"car_index": 0}).json()
    store.close()

    assert body["source_level"] == "RAW"
    assert body["data"]["m_speed"] == 250
    assert body["data"]["m_gear"] == 4


def test_laps_envelope(tmp_path):
    store = ExperimentStore(tmp_path / "t.sqlite3")
    entries = [(95000, 123, 0, 500, 0, 377, 0, 0x01)]
    store.save(_make_packet(build_session_history_datagram(lap_entries=entries, num_laps=1)))
    with TestClient(create_app(Service(store))) as client:
        body = client.get("/api/laps", params={"car_index": 0}).json()
    store.close()

    assert body["source_level"] == "DERIVED"
    assert len(body["data"]) == 1
    assert body["data"][0]["lap_time"] == pytest.approx(95.0)


def test_compare_endpoint(tmp_path):
    store = ExperimentStore(tmp_path / "t.sqlite3")
    entries = [
        (95000, 123, 0, 500, 0, 377, 0, 0x01),  # lap1 95.0s
        (96000, 130, 0, 510, 0, 380, 0, 0x01),  # lap2 96.0s
        (94000, 120, 0, 490, 0, 370, 0, 0x01),  # lap3 94.0s
    ]
    store.save(_make_packet(build_session_history_datagram(lap_entries=entries, num_laps=3)))
    with TestClient(create_app(Service(store))) as client:
        r = client.post(
            "/api/compare",
            json={"car_index": 0, "baseline_laps": [1, 2], "test_laps": [3]},
        )
        body = r.json()
    store.close()

    assert r.status_code == 200
    assert body["source_level"] == "DERIVED"
    assert body["data"]["best_delta_s"] == pytest.approx(-1.0)
    assert body["data"]["baseline_n"] == 2
    assert body["data"]["test_n"] == 1


def test_experiments_endpoint_empty(tmp_path):
    store = ExperimentStore(tmp_path / "t.sqlite3")
    with TestClient(create_app(Service(store))) as client:
        body = client.get("/api/experiments").json()
    store.close()

    assert body["source_level"] == "DERIVED"
    assert body["data"] == []


# ---------------------------------------------------------------------------
# POST /api/ask：AI 对话（fake client 离线测，不联网）
# ---------------------------------------------------------------------------

class _FakeBlock:
    def __init__(self, type_, **kw):
        self.type = type_
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content


class _FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, responses):
        self.messages = _FakeMessages(responses)


def test_ask_endpoint(tmp_path):
    store = ExperimentStore(tmp_path / "t.sqlite3")
    store.save(_make_packet(build_session_datagram(weather=3)))

    resp1 = _FakeResponse(
        "tool_use",
        [_FakeBlock("tool_use", name="get_session", id="toolu_1", input={})],
    )
    resp2 = _FakeResponse(
        "end_turn", [_FakeBlock("text", text="天气是 clear（weather=3）")]
    )
    claude = ClaudeRaceEngineer(store, client=_FakeClient([resp1, resp2]))
    service = Service(store, claude=claude)

    with TestClient(create_app(service)) as client:
        r = client.post("/api/ask", json={"question": "现在天气如何？"})
        body = r.json()
    store.close()

    assert r.status_code == 200
    assert "3" in body["answer"]


# ---------------------------------------------------------------------------
# WebSocket /ws：实时遥测推送
# ---------------------------------------------------------------------------

def test_ws_live_telemetry(tmp_path):
    store = ExperimentStore(tmp_path / "t.sqlite3")
    service = Service(store)

    with TestClient(create_app(service)) as client:
        with client.websocket_connect("/ws") as ws:
            hello = ws.receive_json()
            assert hello["type"] == "hello"
            assert hello["packet_count"] == 0

            service.ingest(_make_packet(build_car_telemetry_datagram(speed=250)))
            event = ws.receive_json()
            assert event["type"] == "telemetry"
            assert event["packet"] == "car_telemetry"
            assert event["data"]["m_speed"] == 250
    store.close()
