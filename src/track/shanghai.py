"""上海国际赛车场（Shanghai International Circuit）—— 种子赛道。

弯号（16 个）/ 名称（T1–T16）/ 赛道全长 5.451 km = **GAME_DATA**（公开赛道资料）。
lapDistance 起止为**均匀等分估算**（HYPOTHESIS 占位）——弯角并非均匀分布，这里只为
打通数据层与分段链路，后续需用真实 `m_lapDistance` 跑圈数据或官方赛道图标定后替换。
"""

from __future__ import annotations

from track.models import CornerDefinition, Track
from track.registry import register

_TRACK_LENGTH_M = 5451.0
_NUM_CORNERS = 16


def _uniform_boundaries(n: int, total: float) -> list[tuple[float, float]]:
    step = total / n
    return [(round(i * step, 1), round((i + 1) * step, 1)) for i in range(n)]


def build_shanghai() -> Track:
    bounds = _uniform_boundaries(_NUM_CORNERS, _TRACK_LENGTH_M)
    corners = [
        CornerDefinition(
            corner_number=i + 1,
            name=f"T{i + 1}",
            lap_distance_start=start,
            lap_distance_end=end,
        )
        for i, (start, end) in enumerate(bounds)
    ]
    return Track(
        track_id="shanghai",
        name="上海国际赛车场",
        track_length_m=_TRACK_LENGTH_M,
        corners=corners,
        source=(
            "弯号/名称/全长 = GAME_DATA（公开赛道资料）；"
            "lapDistance 起止 = HYPOTHESIS（均匀等分占位，待真实数据标定）"
        ),
    )


register(build_shanghai())
