"""F1_25_2026 帧解析（PHASE 1）：仅解析 header + 保留原始 payload，不做校验。

校验已迁移到 L2 校验层：src/validate/（框架）+ protocol/f1_25_2026/validate.py（规则）。
本文件只负责把一帧 datagram 拆成 header + payload，payload 原样保留（不二次加工）。
"""

from __future__ import annotations

from dataclasses import dataclass

from store.schemas import PacketHeader

from protocol.f1_25_2026.header import parse_header


@dataclass(frozen=True)
class ParseResult:
    """解析产物：header（可能为 None）+ 原始 payload（原样保留）。"""

    header: PacketHeader | None
    payload: bytes


def parse_packet(data: bytes) -> ParseResult:
    """解析 29 字节 header；datagram < 29 时 header 为 None。payload 原样保留。"""
    return ParseResult(header=parse_header(data), payload=data)
