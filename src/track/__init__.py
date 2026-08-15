"""赛道数据层（architecture.md §4）—— 独立模块，不塞进 UDP 接收。

提供 Track / CornerDefinition 模型 + 内存注册表（get_track / list_tracks / register）。
种子赛道见 shanghai.py；弯角几何用 `m_lapDistance`（沿赛道里程，米）区间定义。

PHASE 13：`track_ids.py` 提供 m_trackId（Session packet，int）→ track_id（registry 键）
的官方映射（GAME_DATA，VERIFIED 附录），供 Session → 赛道解析。
"""

from track.models import CornerDefinition, Track
from track.registry import get_track, list_tracks, register
from track.track_ids import TRACK_IDS, TRACK_NAMES, track_id_for, track_name_for

# import 期副作用：把内置种子赛道写进注册表
from track import shanghai  # noqa: F401

__all__ = [
    "Track",
    "CornerDefinition",
    "get_track",
    "list_tracks",
    "register",
    "TRACK_IDS",
    "TRACK_NAMES",
    "track_id_for",
    "track_name_for",
]
