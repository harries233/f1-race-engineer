"""赛道注册表（内存）—— 按 track_id 查找赛道定义。

种子赛道在 `track/__init__.py` import 期注册；新增赛道可 `register()` 追加。
"""

from __future__ import annotations

from track.models import Track

_TRACKS: dict[str, Track] = {}


def register(track: Track) -> None:
    """注册（或覆盖）一条赛道定义。"""
    _TRACKS[track.track_id] = track


def get_track(track_id: str) -> Track | None:
    """按 id 取赛道；未知返回 None。"""
    return _TRACKS.get(track_id)


def list_tracks() -> list[Track]:
    """已注册的全部赛道定义。"""
    return list(_TRACKS.values())
