"""Unit tests：StructuredPacketStore（结构化入库，PHASE 5）。"""

import json
import sqlite3

import pytest

from ingest.receiver import TelemetryReceiver
from mock.factory import (
    build_car_telemetry_datagram,
    build_datagram,
    build_session_datagram,
)
from store.structured_store import StructuredPacketStore

DEFAULT_SESSION_UID = 0x1122334455667788

# 9 个 per-car 包（展开 24 车）+ 8 个全局包（单行）。
CAR_PACKETS = {0, 2, 4, 5, 6, 7, 8, 9, 10, 16}
GLOBAL_PACKETS = {1, 3, 11, 12, 13, 14, 15}

EXPECTED_TABLES = {
    0: "packet_motion",
    1: "packet_session",
    2: "packet_lap_data",
    3: "packet_event",
    4: "packet_participants",
    5: "packet_car_setups",
    6: "packet_car_telemetry",
    7: "packet_car_status",
    8: "packet_final_classification",
    9: "packet_lobby_info",
    10: "packet_car_damage",
    11: "packet_session_history",
    12: "packet_tyre_sets",
    13: "packet_motion_ex",
    14: "packet_time_trial",
    15: "packet_lap_positions",
    16: "packet_car_telemetry_2",
}


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "telemetry.sqlite3"


def _make_packet(datagram):
    receiver = TelemetryReceiver(port=12345)  # 仅构造，不 bind
    return receiver._to_packet(datagram, ("192.168.1.10", 51234))


def _query(db_path, sql, params=()):
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_all_packet_types_persist_expected_rows(db_path):
    store = StructuredPacketStore(db_path)
    for packet_id in range(17):
        store.save(_make_packet(build_datagram(packet_id)))

    assert set(store.table_names()) == set(EXPECTED_TABLES.values())
    for packet_id in range(17):
        table = EXPECTED_TABLES[packet_id]
        expected = 24 if packet_id in CAR_PACKETS else 1
        assert store.rows_in(table) == expected, table
    assert store.structured_row_count() == 10 * 24 + 7
    store.close()


def test_car_telemetry_fields_and_car_index(db_path):
    store = StructuredPacketStore(db_path)
    store.save(_make_packet(build_car_telemetry_datagram(speed=250, throttle=0.8)))
    store.close()

    row = _query(
        db_path,
        "SELECT car_index, m_speed, m_throttle, m_brakesTemperature, m_mfdPanelIndex "
        "FROM packet_car_telemetry WHERE car_index=0",
    )[0]
    assert row[0] == 0
    assert row[1] == 250
    assert row[2] == pytest.approx(0.8)          # float32 round-trip
    assert json.loads(row[3]) == [0, 0, 0, 0]    # 数组字段 JSON 化
    assert row[4] == 0                           # 顶层标量随行重复（零填充）


def test_session_global_packet_single_row(db_path):
    store = StructuredPacketStore(db_path)
    store.save(_make_packet(build_session_datagram(weather=2)))
    store.close()

    row = _query(db_path, "SELECT m_weather, m_marshalZones FROM packet_session")[0]
    assert row[0] == 2
    assert len(json.loads(row[1])) == 21         # 内嵌模型列表 → JSON


def test_structured_rows_carry_envelope_and_fk(db_path):
    store = StructuredPacketStore(db_path)
    packet = _make_packet(build_datagram(6))
    raw_id = store.save(packet)
    store.close()

    row = _query(
        db_path,
        "SELECT raw_packet_id, source_level, source, unit, confidence, session_uid "
        "FROM packet_car_telemetry WHERE car_index=0",
    )[0]
    assert row[0] == raw_id                      # 外键指向 raw 帧
    assert row[1] == "RAW"
    assert row[2] == "udp:packet:car_telemetry"
    assert row[3] == "raw"
    assert row[4] == "HIGH"
    assert row[5] == DEFAULT_SESSION_UID


def test_failed_packet_no_structured_rows(db_path):
    store = StructuredPacketStore(db_path)
    packet = _make_packet(build_datagram(6, packet_format=2025))  # → ERROR
    assert packet.structured is None
    store.save(packet)

    assert store.table_names() == []             # 未建结构化表
    assert store.structured_row_count() == 0
    assert store.count() == 1                    # 原始帧仍入库（不丢弃）
    store.close()


def test_receiver_wire_to_structured_store(db_path):
    store = StructuredPacketStore(db_path)
    receiver = TelemetryReceiver(port=12345, on_packet=store.save)
    packet = receiver._to_packet(build_datagram(6), ("127.0.0.1", 5000))
    receiver.on_packet(packet)                   # 模拟 serve_forever 的每帧回调

    assert store.count() == 1
    assert store.structured_row_count() == 24
