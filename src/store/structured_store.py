"""L3 数据层 —— 结构化入库实现（PHASE 5）。

把 PHASE 4 解析出的类型化 payload（经 protocol 层打平成 `StructuredTable` DTO）
落进 SQLite 真实列，让 L4/L5 能按列查询遥测数据，而非只有原始 BLOB。

设计：
  - `StructuredPacketStore` 继承 `PacketStore`，复用同一连接 + raw_packets/validation_issues
    的入库逻辑；`save(packet)` 先落原始帧（`super().save`），再落结构化行。
  - 每个 packet 类型一张表（`packet_<name>`），惰性建表；公共列带数据信封
    （source_level/source/timestamp/unit/confidence）+ raw_packets 外键做可追溯。
  - 打平边界（见 protocol/f1_25_2026/flatten.py）：标量→列，per-car 数组→每车一行，
    嵌套集合→JSON 文本列。

约定：
  - 结构化行是 RAW 级（直接从 UDP 解析，无计算）：source_level=RAW、unit="raw"
    （行内混单位 km/h/°C/psi，逐字段单位在官方 Spec）、confidence=HIGH。
  - `count()` 沿用 raw 帧数；结构化行数用 `structured_row_count()`。
"""

from __future__ import annotations

from pathlib import Path

from store.schemas import RawPacket, StructuredTable
from store.sqlite_store import PacketStore

# 公共列（除 id 外；id 由 AUTOINCREMENT 生成）。data 信封 5 字段 + 上下文 + 外键。
_COMMON_COLUMNS: tuple[tuple[str, str], ...] = (
    ("raw_packet_id", "INTEGER NOT NULL REFERENCES raw_packets(id) ON DELETE CASCADE"),
    ("received_at", "TEXT"),
    ("session_uid", "INTEGER"),
    ("frame_identifier", "INTEGER"),
    ("overall_frame_identifier", "INTEGER"),
    ("source_level", "TEXT"),
    ("source", "TEXT"),
    ("timestamp", "TEXT"),
    ("unit", "TEXT"),
    ("confidence", "TEXT"),
)


class StructuredPacketStore(PacketStore):
    """SQLite 持久化：raw_packets（继承）+ 每 packet 类型一张结构化表。"""

    def __init__(self, db_path: str | Path) -> None:
        super().__init__(db_path)
        self._structured_tables: set[str] = set()

    def save(self, packet: RawPacket) -> int:
        """落原始帧 +（若有）结构化行，返回 raw_packets 行 id。"""
        raw_id = super().save(packet)
        if packet.structured is not None and packet.header is not None:
            self._save_structured(raw_id, packet, packet.structured)
        return raw_id

    # ------------------------------------------------------------------
    # 结构化入库
    # ------------------------------------------------------------------

    def _save_structured(self, raw_id: int, packet: RawPacket, structured: StructuredTable) -> None:
        self._ensure_table(structured)
        header = packet.header
        source = "udp:packet:" + structured.table_name.removeprefix("packet_")

        columns = [name for name, _ in _COMMON_COLUMNS] + list(structured.columns)
        insert_sql = (
            f"INSERT INTO {structured.table_name} ({', '.join(columns)}) "
            f"VALUES ({', '.join(['?'] * len(columns))})"
        )
        common = (
            raw_id,
            packet.received_at,
            header.m_sessionUID,
            header.m_frameIdentifier,
            header.m_overallFrameIdentifier,
            "RAW",          # source_level：结构化行恒为 RAW（直接解析自 UDP，无计算）
            source,
            packet.timestamp,
            "raw",          # unit：行内混单位（km/h/°C/psi），逐字段单位在官方 Spec
            "HIGH",         # confidence
        )
        for row in structured.rows:
            self._conn.execute(insert_sql, common + tuple(row))
        self._conn.commit()

    def _ensure_table(self, structured: StructuredTable) -> None:
        if structured.table_name in self._structured_tables:
            return
        column_defs = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
        column_defs += [f"{name} {typ}" for name, typ in _COMMON_COLUMNS]
        column_defs += [
            f"{name} {typ}"
            for name, typ in zip(structured.columns, structured.column_types)
        ]
        ddl = (
            f"CREATE TABLE IF NOT EXISTS {structured.table_name} "
            f"({', '.join(column_defs)})"
        )
        self._conn.execute(ddl)
        self._structured_tables.add(structured.table_name)

    # ------------------------------------------------------------------
    # 查询辅助（测试/健康检查）
    # ------------------------------------------------------------------

    def table_names(self) -> list[str]:
        """已建的结构化表名（`packet_*`）。"""
        rows = self._conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name LIKE 'packet_%' ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows]

    def rows_in(self, table: str) -> int:
        """某结构化表的行数。"""
        return self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def structured_row_count(self) -> int:
        """所有结构化表的总行数。"""
        return sum(self.rows_in(t) for t in self.table_names())
