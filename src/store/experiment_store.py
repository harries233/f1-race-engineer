"""L3 数据层 —— 实验与 Setup 快照持久化（PHASE 8）。

把 `SetupSnapshot` 与 `Experiment`（PHASE 4 已定义 Schema，此前只定义未落库）、
`SetupRecommendation`（PHASE 12）持久化到 SQLite。继承 `StructuredPacketStore`，
复用同一连接 + raw/结构化入库逻辑，新增三张表：

  - setup_snapshots：一次 Setup 快照（版本化，供 A/B 实验引用）。
  - experiments：一次 A-B 实验（BASELINE/TEST 圈号集合 + delta_metrics + status）。
  - recommendations：一条 Setup 推荐（SetupParams + rationale + evidence，PHASE 12）。

持久化策略：整条 Pydantic 模型 `model_dump_json()` 存 `data` TEXT 列（含 5 字段
数据信封），另抽出自然键（setup_version / exp_id / status）作独立列便于查询。
读取用 `model_validate_json()` 还原，信封与字段一个不少。

约定：本 store 的写入来自 Tool 层（save_setup / validate_setup），只落确定性数据，
不落 MOCK；`source_level` 按来源由 Tool 层决定（Setup=GAME_DATA / Experiment=DERIVED）。
"""

from __future__ import annotations

from pathlib import Path

from store.schemas import Experiment, SetupRecommendation, SetupSnapshot
from store.structured_store import StructuredPacketStore

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS setup_snapshots (
    setup_version TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experiments (
    exp_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    data TEXT NOT NULL
);
"""


class ExperimentStore(StructuredPacketStore):
    """SQLite 持久化：raw_packets + 结构化表（继承）+ setup_snapshots + experiments。"""

    def __init__(self, db_path: str | Path) -> None:
        super().__init__(db_path)
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Setup 快照
    # ------------------------------------------------------------------

    def save_setup(self, snapshot: SetupSnapshot) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO setup_snapshots (setup_version, data) VALUES (?, ?)",
            (snapshot.setup_version, snapshot.model_dump_json()),
        )
        self._conn.commit()

    def get_setup(self, setup_version: str) -> SetupSnapshot | None:
        row = self._conn.execute(
            "SELECT data FROM setup_snapshots WHERE setup_version = ?", (setup_version,)
        ).fetchone()
        return SetupSnapshot.model_validate_json(row[0]) if row else None

    def list_setups(self) -> list[SetupSnapshot]:
        rows = self._conn.execute(
            "SELECT data FROM setup_snapshots ORDER BY setup_version"
        ).fetchall()
        return [SetupSnapshot.model_validate_json(r[0]) for r in rows]

    # ------------------------------------------------------------------
    # 实验
    # ------------------------------------------------------------------

    def save_experiment(self, experiment: Experiment) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO experiments (exp_id, status, data) VALUES (?, ?, ?)",
            (experiment.exp_id, experiment.status.value, experiment.model_dump_json()),
        )
        self._conn.commit()

    def get_experiment(self, exp_id: str) -> Experiment | None:
        row = self._conn.execute(
            "SELECT data FROM experiments WHERE exp_id = ?", (exp_id,)
        ).fetchone()
        return Experiment.model_validate_json(row[0]) if row else None

    def list_experiments(self, status: str | None = None) -> list[Experiment]:
        if status is not None:
            rows = self._conn.execute(
                "SELECT data FROM experiments WHERE status = ? ORDER BY exp_id", (status,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT data FROM experiments ORDER BY exp_id"
            ).fetchall()
        return [Experiment.model_validate_json(r[0]) for r in rows]

    # ------------------------------------------------------------------
    # Setup 推荐（PHASE 12）
    # ------------------------------------------------------------------

    def save_recommendation(self, recommendation: SetupRecommendation) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO recommendations (recommendation_id, status, data) VALUES (?, ?, ?)",
            (
                recommendation.recommendation_id,
                recommendation.status.value,
                recommendation.model_dump_json(),
            ),
        )
        self._conn.commit()

    def get_recommendation(self, recommendation_id: str) -> SetupRecommendation | None:
        row = self._conn.execute(
            "SELECT data FROM recommendations WHERE recommendation_id = ?",
            (recommendation_id,),
        ).fetchone()
        return SetupRecommendation.model_validate_json(row[0]) if row else None

    def list_recommendations(self, status: str | None = None) -> list[SetupRecommendation]:
        if status is not None:
            rows = self._conn.execute(
                "SELECT data FROM recommendations WHERE status = ? ORDER BY recommendation_id",
                (status,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT data FROM recommendations ORDER BY recommendation_id"
            ).fetchall()
        return [SetupRecommendation.model_validate_json(r[0]) for r in rows]
