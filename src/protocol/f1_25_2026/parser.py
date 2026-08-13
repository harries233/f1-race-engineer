"""F1_25_2026 基础 Packet Validation（PHASE 1/2 最小校验链）。

校验项（对应官方 Spec 已确认事实，见 docs/architecture.md）：
  1. datagram 长度（< 29 无法解析 header）
  2. packetFormat == 2026
  3. packetId ∈ [0, 16]
  4. packetVersion == 1
  5. datagram 长度 == registry 的 expected_size
  6. sessionUID 基本有效性（非 0）
  7. frameIdentifier 类型（uint32）
  8. overallFrameIdentifier 类型（uint32）

任何一项失败 → VALIDATION_FAILED；原始 datagram 由上层保留，不丢弃、不截断、
不补零、不自动修复。
"""

from __future__ import annotations

from dataclasses import dataclass

from store.schemas import PacketHeader, PacketValidationStatus

from protocol.f1_25_2026.header import HEADER_SIZE, PACKET_FORMAT, parse_header
from protocol.f1_25_2026.packets import get_packet_definition, is_valid_packet_id

EXPECTED_PACKET_VERSION = 1


@dataclass(frozen=True)
class ValidationResult:
    """单帧校验结果：status + 失败原因列表（人类可读）。"""

    status: PacketValidationStatus
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParseResult:
    """解析产物：header（可能为 None）+ 原始 payload + 校验结果。"""

    header: PacketHeader | None
    payload: bytes
    validation: ValidationResult


def validate_datagram(data: bytes, header: PacketHeader | None) -> ValidationResult:
    """对一帧 datagram 执行基础校验，返回 ValidationResult。"""
    # 1. datagram 长度：< 29 无法解析 header，直接失败
    if header is None:
        return ValidationResult(
            PacketValidationStatus.VALIDATION_FAILED,
            (f"datagram length {len(data)} < header size {HEADER_SIZE}",),
        )

    issues: list[str] = []

    # 2. packetFormat == 2026
    if header.m_packetFormat != PACKET_FORMAT:
        issues.append(f"packetFormat {header.m_packetFormat} != {PACKET_FORMAT}")

    # 3. packetId ∈ [0, 16]
    packet_id = header.m_packetId
    if not is_valid_packet_id(packet_id):
        issues.append(f"packetId {packet_id} out of range [0, 16]")
    else:
        # 5. datagram 长度 == expected_size（记录 packet_id/expected/actual/difference）
        definition = get_packet_definition(packet_id)
        assert definition is not None  # is_valid_packet_id 已保证在 registry 内
        expected_size = definition.expected_size
        actual_size = len(data)
        if actual_size != expected_size:
            issues.append(
                f"packet_size mismatch: packet_id={packet_id} "
                f"expected_size={expected_size} actual_size={actual_size} "
                f"difference={actual_size - expected_size}"
            )

    # 4. packetVersion == 1
    if header.m_packetVersion != EXPECTED_PACKET_VERSION:
        issues.append(
            f"packetVersion {header.m_packetVersion} != {EXPECTED_PACKET_VERSION}"
        )

    # 6. sessionUID 基本有效性（非 0）
    if header.m_sessionUID == 0:
        issues.append("sessionUID == 0 (无有效会话)")

    # 7/8. frameIdentifier / overallFrameIdentifier 类型（uint32 范围）
    if not (0 <= header.m_frameIdentifier <= 0xFFFFFFFF):
        issues.append(f"frameIdentifier {header.m_frameIdentifier} out of uint32 range")
    if not (0 <= header.m_overallFrameIdentifier <= 0xFFFFFFFF):
        issues.append(
            f"overallFrameIdentifier {header.m_overallFrameIdentifier} out of uint32 range"
        )

    status = (
        PacketValidationStatus.VALID
        if not issues
        else PacketValidationStatus.VALIDATION_FAILED
    )
    return ValidationResult(status, tuple(issues))


def parse_packet(data: bytes) -> ParseResult:
    """解析 header 并执行基础校验。"""
    header = parse_header(data)
    validation = validate_datagram(data, header)
    return ParseResult(header=header, payload=data, validation=validation)
