"""F1_25_2026 payload 打平（PHASE 5）。

把 `payload.py` 解析出的类型化 Pydantic 模型，打平成一张张关系表的中性 DTO
（`store.schemas.StructuredTable`），供 `store/structured_store.py` 落 SQLite 列。

分层约定：打平逻辑留在 protocol 层（这里认识每种 packet 的结构），store 只消费
中性 DTO，避免 store → protocol 的反向依赖。

打平边界（PHASE 5）：
  - 标量字段（int/float/str）→ 真实列。
  - per-car 数组（`list[CarXxxData]`，24 车）→ 展开成每车一行，加 `car_index` 列；
    顶层标量字段随行重复（本 phase 不拆第二张 packet 级表）。
  - 嵌套集合（数组 `list[int]`/`list[float]`、内嵌模型列表、dict、`list[list[int]]`）
    → JSON 文本列。深度归一化成子表留给后续 phase。
"""

from __future__ import annotations

import json
from typing import get_origin

from pydantic import BaseModel

from protocol.f1_25_2026.packets import get_packet_definition
from protocol.f1_25_2026.payload import (
    PacketCarDamageData,
    PacketCarSetupData,
    PacketCarStatusData,
    PacketCarTelemetry2Data,
    PacketCarTelemetryData,
    PacketEventData,
    PacketFinalClassificationData,
    PacketLapData,
    PacketLapPositionsData,
    PacketLobbyInfoData,
    PacketMotionData,
    PacketMotionExData,
    PacketParticipantsData,
    PacketSessionData,
    PacketSessionHistoryData,
    PacketTimeTrialData,
    PacketTyreSetsData,
)
from store.schemas import StructuredTable

# ---------------------------------------------------------------------------
# packet 形状：per-car 包 → (model_cls, car 数组字段名)；全局包 → model_cls
# ---------------------------------------------------------------------------

_CAR_SHAPES: dict[int, tuple[type[BaseModel], str]] = {
    0: (PacketMotionData, "m_carMotionData"),
    2: (PacketLapData, "m_lapData"),
    4: (PacketParticipantsData, "m_participants"),
    5: (PacketCarSetupData, "m_carSetupData"),
    6: (PacketCarTelemetryData, "m_carTelemetryData"),
    7: (PacketCarStatusData, "m_carStatusData"),
    8: (PacketFinalClassificationData, "m_classificationData"),
    9: (PacketLobbyInfoData, "m_lobbyPlayers"),
    10: (PacketCarDamageData, "m_carDamageData"),
    16: (PacketCarTelemetry2Data, "m_carTelemetry2Data"),
}

_GLOBAL_SHAPES: dict[int, type[BaseModel]] = {
    1: PacketSessionData,
    3: PacketEventData,
    11: PacketSessionHistoryData,
    12: PacketTyreSetsData,
    13: PacketMotionExData,
    14: PacketTimeTrialData,
    15: PacketLapPositionsData,
}


def _table_name(packet_id: int) -> str:
    """由官方 registry 的 packet_name 派生表名（packet_<snake_case>）。"""
    return "packet_" + get_packet_definition(packet_id).packet_name.lower().replace(" ", "_")


def _sqlite_type(annotation) -> str:
    """把字段注解映射成 SQLite 列类型。嵌套/集合 → TEXT（JSON）。"""
    if get_origin(annotation) is not None:
        return "TEXT"                       # list[...] / list[list[...]] 等 → JSON
    if annotation is int or annotation is bool:
        return "INTEGER"
    if annotation is float:
        return "REAL"
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return "TEXT"                       # 内嵌单模型 → JSON
    return "TEXT"                           # str / dict / 其它 → TEXT


def _reflect_fields(model_cls: type[BaseModel]) -> list[tuple[str, str]]:
    """按声明顺序取字段名 + SQLite 类型（Pydantic v2 model_fields 保序）。"""
    return [(name, _sqlite_type(field.annotation)) for name, field in model_cls.model_fields.items()]


def _plain(v):
    """把 Pydantic 模型/列表/dict 递归转成 JSON 可序列化的纯 Python 对象。"""
    if isinstance(v, BaseModel):
        return v.model_dump()
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {k: _plain(val) for k, val in v.items()}
    return v


def _json_value(v):
    """标量原样返回；集合/模型 → JSON 字符串（TEXT 列）。"""
    if isinstance(v, (BaseModel, list, tuple, dict)):
        return json.dumps(_plain(v))
    return v


def _flatten_car(table_name: str, model_cls, car_field: str, payload) -> StructuredTable:
    cars = getattr(payload, car_field)
    car_fields = _reflect_fields(type(cars[0]))
    top_fields = [(n, t) for (n, t) in _reflect_fields(model_cls) if n != car_field]

    columns = ("car_index",) + tuple(n for n, _ in car_fields) + tuple(n for n, _ in top_fields)
    column_types = ("INTEGER",) + tuple(t for _, t in car_fields) + tuple(t for _, t in top_fields)

    rows = []
    for i, car in enumerate(cars):
        row = [i]
        row.extend(_json_value(getattr(car, n)) for n, _ in car_fields)
        row.extend(_json_value(getattr(payload, n)) for n, _ in top_fields)
        rows.append(tuple(row))

    return StructuredTable(
        table_name=table_name,
        columns=columns,
        column_types=column_types,
        rows=tuple(rows),
    )


def _flatten_global(table_name: str, model_cls, payload) -> StructuredTable:
    fields = _reflect_fields(model_cls)
    columns = tuple(n for n, _ in fields)
    column_types = tuple(t for _, t in fields)
    row = tuple(_json_value(getattr(payload, n)) for n, _ in fields)
    return StructuredTable(
        table_name=table_name,
        columns=columns,
        column_types=column_types,
        rows=(row,),
    )


def flatten_payload(packet_id: int, payload) -> StructuredTable | None:
    """把一帧 payload 打平成 StructuredTable；未知 packetId / 类型不符返回 None。"""
    if get_packet_definition(packet_id) is None:
        return None
    table_name = _table_name(packet_id)

    if packet_id in _CAR_SHAPES:
        model_cls, car_field = _CAR_SHAPES[packet_id]
        if not isinstance(payload, model_cls) or not getattr(payload, car_field):
            return None
        return _flatten_car(table_name, model_cls, car_field, payload)

    model_cls = _GLOBAL_SHAPES.get(packet_id)
    if model_cls is None or not isinstance(payload, model_cls):
        return None
    return _flatten_global(table_name, model_cls, payload)
