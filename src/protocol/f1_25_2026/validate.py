"""F1_25_2026 专属 header 校验规则（L2 具体实现）。

8 项基础校验从 parser.py 原样迁入（均 ERROR），另加 2 项 header 范围校验（WARN）。
规则依据官方 Spec 已确认事实（docs/architecture.md §VERIFIED）：
  - Header = 29 字节，packed，little-endian（<HBBBBBQfIIBB）
  - packetFormat = 2026、packetVersion = 1、packetId ∈ [0,16]
  - 17 个 packet 的 expected_size（packets.PACKET_REGISTRY）
  - playerCarIndex 0..21（22 车，GAME_DATA）；secondaryPlayerCarIndex 0..21 或 255
    （255 = 无第二玩家哨兵，VERIFIED：真实数据 + header 注释）

跨帧顺序校验不在此处，见 validate.frame.FrameValidator（协议无关）。
"""

from __future__ import annotations

from protocol.f1_25_2026.header import HEADER_SIZE, PACKET_FORMAT
from protocol.f1_25_2026.packets import get_packet_definition, is_valid_packet_id
from validate.frame import FrameValidator
from validate.report import Severity, ValidationIssue
from validate.rules import FrameContext, ValidationChain

EXPECTED_PACKET_VERSION = 1
MAX_PLAYER_CAR_INDEX = 21   # F1 25 共 22 车（index 0..21），GAME_DATA
SECONDARY_NO_PLAYER = 255   # 无第二玩家哨兵，VERIFIED
UINT32_MAX = 0xFFFFFFFF


def _rule_datagram_too_short(ctx: FrameContext) -> list[ValidationIssue]:
    if ctx.header is None:
        return [
            ValidationIssue(
                "datagram_too_short",
                Severity.ERROR,
                f"datagram length {len(ctx.data)} < header size {HEADER_SIZE}",
            )
        ]
    return []


def _rule_packet_format(ctx: FrameContext) -> list[ValidationIssue]:
    header = ctx.header
    if header is None or header.m_packetFormat == PACKET_FORMAT:
        return []
    return [
        ValidationIssue(
            "packet_format_mismatch",
            Severity.ERROR,
            f"packetFormat {header.m_packetFormat} != {PACKET_FORMAT}",
        )
    ]


def _rule_packet_id(ctx: FrameContext) -> list[ValidationIssue]:
    header = ctx.header
    if header is None or is_valid_packet_id(header.m_packetId):
        return []
    return [
        ValidationIssue(
            "packet_id_out_of_range",
            Severity.ERROR,
            f"packetId {header.m_packetId} out of range [0, 16]",
        )
    ]


def _rule_packet_size(ctx: FrameContext) -> list[ValidationIssue]:
    header = ctx.header
    if header is None or not is_valid_packet_id(header.m_packetId):
        return []
    definition = get_packet_definition(header.m_packetId)
    assert definition is not None  # is_valid_packet_id 已保证在 registry 内
    expected_size = definition.expected_size
    actual_size = len(ctx.data)
    if actual_size == expected_size:
        return []
    return [
        ValidationIssue(
            "packet_size_mismatch",
            Severity.ERROR,
            f"packet_size mismatch: packet_id={header.m_packetId} "
            f"expected_size={expected_size} actual_size={actual_size} "
            f"difference={actual_size - expected_size}",
        )
    ]


def _rule_packet_version(ctx: FrameContext) -> list[ValidationIssue]:
    header = ctx.header
    if header is None or header.m_packetVersion == EXPECTED_PACKET_VERSION:
        return []
    return [
        ValidationIssue(
            "packet_version_mismatch",
            Severity.ERROR,
            f"packetVersion {header.m_packetVersion} != {EXPECTED_PACKET_VERSION}",
        )
    ]


def _rule_session_uid(ctx: FrameContext) -> list[ValidationIssue]:
    header = ctx.header
    if header is None or header.m_sessionUID != 0:
        return []
    return [
        ValidationIssue(
            "session_uid_zero",
            Severity.ERROR,
            "sessionUID == 0 (无有效会话)",
        )
    ]


def _rule_frame_identifier(ctx: FrameContext) -> list[ValidationIssue]:
    header = ctx.header
    if header is None or 0 <= header.m_frameIdentifier <= UINT32_MAX:
        return []
    return [
        ValidationIssue(
            "frame_identifier_out_of_range",
            Severity.ERROR,
            f"frameIdentifier {header.m_frameIdentifier} out of uint32 range",
        )
    ]


def _rule_overall_frame_identifier(ctx: FrameContext) -> list[ValidationIssue]:
    header = ctx.header
    if header is None or 0 <= header.m_overallFrameIdentifier <= UINT32_MAX:
        return []
    return [
        ValidationIssue(
            "overall_frame_identifier_out_of_range",
            Severity.ERROR,
            f"overallFrameIdentifier {header.m_overallFrameIdentifier} out of uint32 range",
        )
    ]


def _rule_player_car_index(ctx: FrameContext) -> list[ValidationIssue]:
    header = ctx.header
    if header is None or 0 <= header.m_playerCarIndex <= MAX_PLAYER_CAR_INDEX:
        return []
    return [
        ValidationIssue(
            "player_car_index_out_of_range",
            Severity.WARN,
            f"playerCarIndex {header.m_playerCarIndex} not in [0, {MAX_PLAYER_CAR_INDEX}]",
        )
    ]


def _rule_secondary_player_car_index(ctx: FrameContext) -> list[ValidationIssue]:
    header = ctx.header
    # secondary 合法值：0..21 或 255（无第二玩家哨兵）
    if (
        header is None
        or 0 <= header.m_secondaryPlayerCarIndex <= MAX_PLAYER_CAR_INDEX
        or header.m_secondaryPlayerCarIndex == SECONDARY_NO_PLAYER
    ):
        return []
    return [
        ValidationIssue(
            "secondary_player_car_index_out_of_range",
            Severity.WARN,
            f"secondaryPlayerCarIndex {header.m_secondaryPlayerCarIndex} "
            f"not in [0, {MAX_PLAYER_CAR_INDEX}] or {SECONDARY_NO_PLAYER}",
        )
    ]


def build_validator() -> FrameValidator:
    """构造 F1_25_2026 校验器：无状态 header 规则链 + 跨帧顺序状态机。"""
    rules = [
        _rule_datagram_too_short,
        _rule_packet_format,
        _rule_packet_id,
        _rule_packet_size,
        _rule_packet_version,
        _rule_session_uid,
        _rule_frame_identifier,
        _rule_overall_frame_identifier,
        _rule_player_car_index,
        _rule_secondary_player_car_index,
    ]
    return FrameValidator(ValidationChain(rules))
