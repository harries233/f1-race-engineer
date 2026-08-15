"""m_trackId（Session packet，int8，-1=unknown）→ track_id 映射表（PHASE 13）。

数据源（VERIFIED，官方 2026 Season Pack Spec 附录「Track IDs」）：
  「Data Output from F1 25 2026 Season Pack (1).pdf」p.27 附录列出完整 int → 赛道名
  映射；Session 结构体注释明文 `int8 m_trackId; // -1 for unknown, see appendix`。
本文件只做「官方附录 → 映射表」的机械转录，不含业务逻辑，也不臆造不在附录里的值。

与赛道数据层（`track`）的关系：
  - `TRACK_IDS` / `TRACK_NAMES`：官方 int → slug / 名称（GAME_DATA，VERIFIED）。
  - `track_id_for(m_track_id)` 返回 registry 键（slug）。只有已注册几何的赛道
    （当前仅 "shanghai"）能被 `get_track()` 取到；其余 slug 无几何 → get_track None。
"""

from __future__ import annotations

# int m_trackId → 赛道名称（官方附录逐条转录；slug 为名称小写下划线归一）
TRACK_NAMES: dict[int, str] = {
    0: "Melbourne",
    2: "Shanghai",
    3: "Sakhir (Bahrain)",
    4: "Catalunya",
    5: "Monaco",
    6: "Montreal",
    7: "Silverstone",
    9: "Hungaroring",
    10: "Spa",
    11: "Monza",
    12: "Singapore",
    13: "Suzuka",
    14: "Abu Dhabi",
    15: "Texas",
    16: "Brazil",
    17: "Austria",
    19: "Mexico",
    20: "Baku (Azerbaijan)",
    26: "Zandvoort",
    27: "Imola",
    29: "Jeddah",
    30: "Miami",
    31: "Las Vegas",
    32: "Losail",
    39: "Silverstone (Reverse)",
    40: "Austria (Reverse)",
    41: "Zandvoort (Reverse)",
    42: "Madrid",
}

# int m_trackId → registry 键（slug）。与 TRACK_NAMES 一一对应。
TRACK_IDS: dict[int, str] = {
    0: "melbourne",
    2: "shanghai",
    3: "sakhir",
    4: "catalunya",
    5: "monaco",
    6: "montreal",
    7: "silverstone",
    9: "hungaroring",
    10: "spa",
    11: "monza",
    12: "singapore",
    13: "suzuka",
    14: "abu_dhabi",
    15: "texas",
    16: "brazil",
    17: "austria",
    19: "mexico",
    20: "baku",
    26: "zandvoort",
    27: "imola",
    29: "jeddah",
    30: "miami",
    31: "las_vegas",
    32: "losail",
    39: "silverstone_reverse",
    40: "austria_reverse",
    41: "zandvoort_reverse",
    42: "madrid",
}


def track_id_for(m_track_id: int) -> str | None:
    """m_trackId（int）→ registry 键（slug）；未知名（含 -1）返回 None。"""
    return TRACK_IDS.get(m_track_id)


def track_name_for(m_track_id: int) -> str | None:
    """m_trackId（int）→ 官方赛道名；未知名（含 -1）返回 None。"""
    return TRACK_NAMES.get(m_track_id)
