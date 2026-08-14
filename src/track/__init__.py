"""赛道数据层（architecture.md §4）—— 独立模块，不塞进 UDP 接收。

提供 Track / CornerDefinition 模型 + 内存注册表（get_track / list_tracks / register）。
种子赛道见 shanghai.py；弯角几何用 `m_lapDistance`（沿赛道里程，米）区间定义。
"""

from track.models import CornerDefinition, Track
from track.registry import get_track, list_tracks, register

# import 期副作用：把内置种子赛道写进注册表
from track import shanghai  # noqa: F401

__all__ = ["Track", "CornerDefinition", "get_track", "list_tracks", "register"]
