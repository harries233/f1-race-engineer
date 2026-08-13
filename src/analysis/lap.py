"""L4 确定性计算 —— 圈速指标（PHASE 4）。

纯 Python 函数，不靠模型。把 payload 解析出的原始字段换算成 `LapRecord`
（DERIVED，带 5 字段数据信封）。

关键事实（官方 Spec）：
  - LapData（packet 2）只有「当前圈」的 sector1/2 时间 + `lastLapTimeInMS`（上一
    完赛圈），**没有 sector3**、也不含历史完赛圈明细。
  - 完赛圈的完整数据在 SessionHistory（packet 11）的 `LapHistoryData`：含
    sector1/2/3 时间 + `lapValidBitFlags`（bit0x01=lap valid, 0x02/0x04/0x08 =
    sector1/2/3 valid）。
  - 因此 `build_lap_record` 以 `LapHistoryData` 为完赛圈权威来源，而非 LapData。
"""

from __future__ import annotations

from protocol.f1_25_2026.payload import LapHistoryData
from store.schemas import Confidence, LapRecord, SourceLevel

_LAP_VALID_BIT = 0x01


def sector_time_seconds(minutes_part: int, ms_part: int) -> float:
    """分段时间：`min*60 + ms/1000` 秒（Spec 把分段时间拆成整分钟 + 毫秒两部分）。"""
    return minutes_part * 60.0 + ms_part / 1000.0


def lap_time_seconds(last_lap_time_ms: int) -> float:
    """圈速：毫秒 → 秒。"""
    return last_lap_time_ms / 1000.0


def lap_valid_from_bitflags(bit_flags: int) -> bool:
    """由 LapHistoryData.m_lapValidBitFlags 的 bit0 判断整圈是否有效。"""
    return bool(bit_flags & _LAP_VALID_BIT)


def build_lap_record(
    lap_history: LapHistoryData,
    *,
    lap_number: int,
    session_uid: int,
    received_at: str,
    setup_version: str | None = None,
) -> LapRecord:
    """由 SessionHistory 的完赛圈明细构造 LapRecord（DERIVED）。

    参数：
      lap_history：完赛圈明细（sector1/2/3 时间 + valid bit flags）。
      lap_number：该圈圈号（LapHistoryData 本身不含圈号，由数组位置决定）。
      session_uid：会话 id。
      received_at：UTC ISO8601（作为信封 timestamp）。
      setup_version：可选，指向 SetupSnapshot.setup_version 做可追溯。
    """
    return LapRecord(
        source_level=SourceLevel.DERIVED,
        source="calc:lap_metrics",
        timestamp=received_at,
        unit="s",
        confidence=Confidence.HIGH,
        lap_number=lap_number,
        session_uid=session_uid,
        lap_time=lap_time_seconds(lap_history.m_lapTimeInMS),
        sector1=sector_time_seconds(
            lap_history.m_sector1TimeMinutesPart, lap_history.m_sector1TimeMSPart
        ),
        sector2=sector_time_seconds(
            lap_history.m_sector2TimeMinutesPart, lap_history.m_sector2TimeMSPart
        ),
        sector3=sector_time_seconds(
            lap_history.m_sector3TimeMinutesPart, lap_history.m_sector3TimeMSPart
        ),
        valid_flag=lap_valid_from_bitflags(lap_history.m_lapValidBitFlags),
        setup_version=setup_version,
    )
