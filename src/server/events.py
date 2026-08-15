"""实时遥测事件提取（PHASE 14）。

从一帧 `RawPacket` 的 `structured`（PHASE 5 已解析打平的结构化表）提取「仪表盘相关」
packet 的玩家车行，包装成带 RAW 信封的实时事件 dict，供 WebSocket 推给手机。

只挑 4 类仪表盘相关 packet，避免把全部 17 种 packet 都推给手机刷屏：
  - session（packet 1，全局单结构）：天气/温度/赛道/会话类型。
  - lap_data（packet 2，per-car）：当前圈号/扇区/圈里程/圈用时。
  - car_telemetry（packet 6，per-car）：速度/油门/刹车/挡位/转速。
  - car_status（packet 7，per-car）：燃油/ERS/DRS/轮胎。

提取规则：car 包取 `m_playerCarIndex` 那一行（仪表盘只看玩家车），全局包取唯一行。
结构化表里嵌套集合字段已被 flatten 序列化成 JSON 文本列，此处原样透传（客户端按需
json.loads），不做二次解析 —— 服务层不新增计算。
"""

from __future__ import annotations

from typing import Any

from store.schemas import RawPacket

# packet_id → 事件里的人类可读 packet 名
_BROADCAST_PACKETS: dict[int, str] = {
    1: "session",
    2: "lap_data",
    6: "car_telemetry",
    7: "car_status",
}


def build_event(packet: RawPacket) -> dict[str, Any] | None:
    """把一帧 RawPacket 转成实时事件 dict；非广播 packet / 无结构化数据返回 None。"""
    if packet.header is None or packet.structured is None:
        return None
    name = _BROADCAST_PACKETS.get(packet.header.m_packetId)
    if name is None:
        return None

    table = packet.structured
    row = _select_row(table.columns, table.rows, packet.header.m_playerCarIndex)
    if row is None:
        return None

    return {
        "type": "telemetry",
        "packet": name,
        "packet_id": packet.header.m_packetId,
        "session_uid": packet.header.m_sessionUID,
        "session_time": packet.header.m_sessionTime,
        "frame_identifier": packet.header.m_frameIdentifier,
        "overall_frame_identifier": packet.header.m_overallFrameIdentifier,
        "received_at": packet.received_at,
        "source_level": "RAW",
        "car_index": packet.header.m_playerCarIndex,
        "data": dict(zip(table.columns, row)),
    }


def _select_row(
    columns: tuple[str, ...], rows: tuple[tuple[Any, ...], ...], player_car_index: int
) -> tuple[Any, ...] | None:
    """car 包取玩家车行（car_index == player_car_index）；全局包取唯一行。"""
    if not rows:
        return None
    if "car_index" in columns:
        idx = columns.index("car_index")
        return next((r for r in rows if r[idx] == player_car_index), None)
    return rows[0]
