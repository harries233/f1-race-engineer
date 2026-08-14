"""Unit tests：PacketStore（SQLite 入库 RawPacket + 校验报告）。"""

import sqlite3

import pytest

from ingest.receiver import TelemetryReceiver
from mock.factory import build_datagram
from store.sqlite_store import PacketStore

# mock.factory 的默认 header 值（见 tests/mock/factory.py）
DEFAULT_SESSION_UID = 0x1122334455667788
DEFAULT_FRAME_IDENTIFIER = 12345
# 注意：session_time 是 float32（header '<f'），round-trip 后非精确 123.456，
# 故断言直接用 packet.header.m_sessionTime 对账，而非常量。


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


def test_save_persists_valid_packet(db_path):
    store = PacketStore(db_path)
    datagram = build_datagram(6)  # Car Telemetry, packet_id=6
    packet = _make_packet(datagram)
    row_id = store.save(packet)
    store.close()

    assert row_id == 1
    row = _query(
        db_path,
        "SELECT payload, payload_size, validation_status, "
        "source_level, source, unit, confidence, protocol_version, "
        "packet_format, packet_id, session_uid, session_time, "
        "frame_identifier, player_car_index, secondary_player_car_index "
        "FROM raw_packets WHERE id=?",
        (row_id,),
    )[0]
    assert row[0] == datagram                 # payload BLOB 原样保留
    assert row[1] == len(datagram)
    assert row[2] == "VALID"
    assert row[3] == "RAW"                    # 信封 5 字段
    assert row[4] == "udp:raw"
    assert row[5] == "raw_frame"
    assert row[6] == "HIGH"
    assert row[7] == "F1_25_2026"
    assert row[8] == 2026                     # header 字段
    assert row[9] == 6
    assert row[10] == DEFAULT_SESSION_UID
    assert row[11] == packet.header.m_sessionTime   # float32 round-trip 后对账 header 原值
    assert row[12] == DEFAULT_FRAME_IDENTIFIER
    assert row[13] == 0
    assert row[14] == 255


def test_save_persists_validation_issues(db_path):
    store = PacketStore(db_path)
    datagram = build_datagram(6, player_car_index=99)  # → WARN
    packet = _make_packet(datagram)
    assert any(i.code == "player_car_index_out_of_range" for i in packet.validation_issues)

    row_id = store.save(packet)
    store.close()

    rows = _query(
        db_path,
        "SELECT code, severity, message FROM validation_issues WHERE packet_id=?",
        (row_id,),
    )
    assert len(rows) == 1
    assert rows[0][0] == "player_car_index_out_of_range"
    assert rows[0][1] == "WARN"
    assert "playerCarIndex" in rows[0][2]


def test_save_failed_packet_still_persisted(db_path):
    store = PacketStore(db_path)
    datagram = build_datagram(6, packet_format=2025)  # → ERROR, 不丢弃
    packet = _make_packet(datagram)
    row_id = store.save(packet)
    store.close()

    row = _query(
        db_path,
        "SELECT payload, validation_status FROM raw_packets WHERE id=?",
        (row_id,),
    )[0]
    assert row[0] == datagram                 # 校验失败也保留原始 datagram
    assert row[1] == "VALIDATION_FAILED"
    issues = _query(
        db_path,
        "SELECT code FROM validation_issues WHERE packet_id=?",
        (row_id,),
    )
    assert any(code[0] == "packet_format_mismatch" for code in issues)


def test_save_short_datagram_header_null(db_path):
    store = PacketStore(db_path)
    datagram = build_datagram(6, total_size=10)  # < 29 → header is None
    packet = _make_packet(datagram)
    assert packet.header is None
    row_id = store.save(packet)
    store.close()

    row = _query(
        db_path,
        "SELECT payload, payload_size, validation_status, "
        "packet_format, session_uid, frame_identifier "
        "FROM raw_packets WHERE id=?",
        (row_id,),
    )[0]
    assert row[0] == datagram                 # 10 字节 payload 原样
    assert row[1] == 10
    assert row[2] == "VALIDATION_FAILED"
    assert row[3] is None                     # header 各列存 NULL
    assert row[4] is None
    assert row[5] is None


def test_save_returns_incrementing_ids(db_path):
    store = PacketStore(db_path)
    first = store.save(_make_packet(build_datagram(6)))
    second = store.save(_make_packet(build_datagram(6, frame_identifier=12346)))
    assert store.count() == 2
    store.close()

    assert second == first + 1


def test_receiver_wire_to_store(db_path):
    store = PacketStore(db_path)
    receiver = TelemetryReceiver(port=12345, on_packet=store.save)
    packet = receiver._to_packet(build_datagram(6), ("127.0.0.1", 5000))
    receiver.on_packet(packet)  # 模拟 serve_forever 的每帧回调
    assert store.count() == 1


def test_query_returns_dict_rows(db_path):
    store = PacketStore(db_path)
    store.save(_make_packet(build_datagram(6)))
    store.save(_make_packet(build_datagram(6, frame_identifier=12346)))
    rows = store.query(
        "raw_packets",
        where="packet_id = ?",
        params=(6,),
        order_by="frame_identifier DESC",
        limit=1,
    )
    store.close()

    assert len(rows) == 1
    assert rows[0]["packet_id"] == 6
    assert rows[0]["frame_identifier"] == 12346


def test_sessions_groups_by_session_uid(db_path):
    store = PacketStore(db_path)
    store.save(_make_packet(build_datagram(6, session_uid=1)))
    store.save(_make_packet(build_datagram(6, session_uid=2)))
    sessions = store.sessions()
    store.close()

    assert {s["session_uid"] for s in sessions} == {1, 2}
    assert all(s["packet_count"] == 1 for s in sessions)
