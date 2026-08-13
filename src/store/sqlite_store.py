"""L3 数据层 —— SQLite 持久化实现（PHASE 3）。

唯一持久化实现：PacketStore 把 RawPacket（原始帧）+ 校验报告（validation_issues）
落到 SQLite。选型：stdlib sqlite3（零新依赖）。后续 L4 若需列式分析可加
duckdb_store.py 复用同一 save/count/close 接口，不动调用方。

约定：
  - 校验失败帧同样入库（不丢弃），payload BLOB 原样保留。
  - header 可空（datagram < 29 时 header is None）→ header 各列存 NULL。
  - session_uid（uint64）存 INTEGER：F1 sessionUID 由系统时间派生、实际 < 2^63；
    若超出会由 sqlite3 显式抛 OverflowError（fail-loud，不静默截断）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from store.schemas import RawPacket

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS raw_packets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at TEXT NOT NULL,
    source_address TEXT,
    protocol_version TEXT,
    source_level TEXT NOT NULL,
    source TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    unit TEXT NOT NULL,
    confidence TEXT NOT NULL,
    validation_status TEXT NOT NULL,
    packet_format INTEGER,
    game_year INTEGER,
    game_major INTEGER,
    game_minor INTEGER,
    packet_version INTEGER,
    packet_id INTEGER,
    session_uid INTEGER,
    session_time REAL,
    frame_identifier INTEGER,
    overall_frame_identifier INTEGER,
    player_car_index INTEGER,
    secondary_player_car_index INTEGER,
    payload BLOB NOT NULL,
    payload_size INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_raw_packets_session_frame
    ON raw_packets(session_uid, frame_identifier);
CREATE INDEX IF NOT EXISTS idx_raw_packets_packet_id
    ON raw_packets(packet_id);
CREATE TABLE IF NOT EXISTS validation_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    packet_id INTEGER NOT NULL REFERENCES raw_packets(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_validation_issues_packet_id
    ON validation_issues(packet_id);
"""

_PACKET_INSERT_SQL = """
INSERT INTO raw_packets (
    received_at, source_address, protocol_version,
    source_level, source, timestamp, unit, confidence, validation_status,
    packet_format, game_year, game_major, game_minor, packet_version, packet_id,
    session_uid, session_time, frame_identifier, overall_frame_identifier,
    player_car_index, secondary_player_car_index,
    payload, payload_size
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_ISSUE_INSERT_SQL = (
    "INSERT INTO validation_issues (packet_id, code, severity, message) "
    "VALUES (?, ?, ?, ?)"
)


class PacketStore:
    """SQLite 持久化：raw_packets（每帧一行）+ validation_issues（每 issue 一行）。"""

    def __init__(self, db_path: str | Path) -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA_SQL)

    def save(self, packet: RawPacket) -> int:
        """落库一帧 + 其校验报告，commit 后返回 raw_packets 行 id。"""
        header = packet.header
        packet_id = self._conn.execute(
            _PACKET_INSERT_SQL,
            (
                packet.received_at,
                packet.source_address,
                packet.protocol_version.value if packet.protocol_version else None,
                packet.source_level.value,
                packet.source,
                packet.timestamp,
                packet.unit,
                packet.confidence.value,
                packet.validation_status.value,
                header.m_packetFormat if header else None,
                header.m_gameYear if header else None,
                header.m_gameMajorVersion if header else None,
                header.m_gameMinorVersion if header else None,
                header.m_packetVersion if header else None,
                header.m_packetId if header else None,
                header.m_sessionUID if header else None,
                header.m_sessionTime if header else None,
                header.m_frameIdentifier if header else None,
                header.m_overallFrameIdentifier if header else None,
                header.m_playerCarIndex if header else None,
                header.m_secondaryPlayerCarIndex if header else None,
                packet.payload,
                len(packet.payload),
            ),
        ).lastrowid

        for issue in packet.validation_issues:
            self._conn.execute(
                _ISSUE_INSERT_SQL,
                (packet_id, issue.code, issue.severity, issue.message),
            )

        self._conn.commit()
        return packet_id

    def count(self) -> int:
        """已入库帧数（测试/健康检查用）。"""
        return self._conn.execute("SELECT COUNT(*) FROM raw_packets").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
