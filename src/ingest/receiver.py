"""L1 接收层 —— F1 25 UDP Telemetry 接收（PHASE 1）。

职责（严格收敛）：
  - 绑定 UDP socket，收 datagram。
  - 解析 29 字节 header（F1_25_2026 / 2026 Season Pack）。
  - 委托 L2 校验层（src/validate/ + protocol/f1_25_2026/validate.py）做校验。
  - 打 RAW 信封，原样打包成 RawPacket（payload 保留原始 bytes）。

不负责：
  - payload 体解析（字段映射见 protocol/f1_25_2026/）。
  - 入库（L3）、任何计算（L4）。

规则（Master Prompt）：
  - 不硬编码未验证的 UDP 端口：UDP_PORT 必须显式传入，否则报 UDP_PORT_NOT_CONFIGURED。
  - 不生成假数据；测试数据走 tests/mock/ 且标 MOCK_DATA。
  - 校验失败保留原始 datagram，不丢弃。
"""

from __future__ import annotations

import logging
import socket
from typing import Callable, Optional

from protocol.f1_25_2026 import parse_packet
from protocol.f1_25_2026.validate import build_validator
from store.schemas import (
    Confidence,
    ProtocolVersion,
    RawPacket,
    SourceLevel,
    now_utc,
)
from validate.report import Severity

logger = logging.getLogger(__name__)

DEFAULT_HOST = "0.0.0.0"


class UDPPortNotConfiguredError(RuntimeError):
    """UDP 接收端口未配置（官方 Spec 未给默认端口，禁止硬编码 20777）。"""


class TelemetryReceiver:
    """收 UDP datagram → 解析 header → 委托 L2 校验 → RawPacket 回调。"""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: Optional[int] = None,
        on_packet: Optional[Callable[[RawPacket], None]] = None,
    ) -> None:
        if port is None:
            raise UDPPortNotConfiguredError("UDP_PORT_NOT_CONFIGURED")
        self.host = host
        self.port = port
        self.on_packet = on_packet
        self._sock: Optional[socket.socket] = None
        self._validator = build_validator()

    def bind(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind((self.host, self.port))

    def receive_one(self) -> RawPacket:
        """收一帧并返回 RawPacket。"""
        if self._sock is None:
            self.bind()
        data, addr = self._sock.recvfrom(65535)
        return self._to_packet(data, addr)

    def serve_forever(self) -> None:
        """阻塞循环收帧，每帧触发 on_packet 回调，直到 KeyboardInterrupt。"""
        if self._sock is None:
            self.bind()
        while True:
            data, addr = self._sock.recvfrom(65535)
            packet = self._to_packet(data, addr)
            if self.on_packet is not None:
                self.on_packet(packet)

    def _to_packet(self, data: bytes, addr: tuple) -> RawPacket:
        """把一帧原始 datagram 解析 + 委托 L2 校验 + 打包成 RawPacket。

        原始 datagram 原样保留在 payload；校验失败也保留，不丢弃、不修复。
        """
        received_at = now_utc()
        source_address = f"{addr[0]}:{addr[1]}"
        parsed = parse_packet(data)
        report = self._validator.validate(data, parsed.header)

        protocol_version = None
        if parsed.header is not None:
            protocol_version = ProtocolVersion.from_packet_format(
                parsed.header.m_packetFormat
            )

        for issue in report.issues:
            if issue.severity is Severity.ERROR:
                logger.warning("packet validation %s: %s", issue.code, issue.message)
            else:
                logger.debug("packet validation %s: %s", issue.code, issue.message)

        return RawPacket(
            source_level=SourceLevel.RAW,
            source="udp:raw",
            timestamp=received_at,
            unit="raw_frame",
            confidence=Confidence.HIGH,
            protocol_version=protocol_version,
            header=parsed.header,
            payload=data,
            received_at=received_at,
            source_address=source_address,
            validation_status=report.status,
        )
