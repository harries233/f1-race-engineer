"""赛道数据层模型（architecture.md §4）—— 赛道几何与弯角参考点。

F1 25 UDP 遥测**不提供**弯角坐标/刹车点/弯角边界，逐弯分析必须依赖这份独立数据。
弯角用 `m_lapDistance`（沿赛道里程，米）区间定义，避免依赖世界坐标（UDP 的
Motion 世界坐标与赛道弯角的映射同样需要几何数据，且更难对齐）。

诚实性约定：
  - 弯号 / 名称 / 赛道全长：来自公开赛道资料 → `GAME_DATA`。
  - `lapDistance` 起止边界：估算占位 → `HYPOTHESIS`，需真实跑圈数据或官方赛道图
    标定后升级。该不确定性在 `Track.source` 与下游 `CornerRecord.confidence` 里声明。
"""

from __future__ import annotations

from pydantic import BaseModel


class CornerDefinition(BaseModel):
    """一个弯角的定义：弯号 + 名称 + 沿赛道里程的 [start, end) 区间（米）。"""

    corner_number: int
    name: str
    lap_distance_start: float   # m，含
    lap_distance_end: float     # m，不含


class Track(BaseModel):
    """一条赛道的几何定义：全长 + 弯角区间表。

    corners 应覆盖 [0, track_length_m]，且互不重叠；样本按 lapDistance 落到区间，
    间隙/超界样本在分段时被丢弃（不编造归属）。
    """

    track_id: str
    name: str
    track_length_m: float
    corners: list[CornerDefinition]
    source: str = ""            # 几何来源说明（GAME_DATA / HYPOTHESIS 标注）
