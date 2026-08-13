"""跨帧顺序校验状态机（协议无关）。

作用于 PacketHeader 公共字段（sessionUID / frameIdentifier / sessionTime），
检测帧序乱序、重复投递、sessionTime 回退、会话边界。这些字段在 F1_25_2026 与
F1_25_BASE 的 header 里均存在，故本状态机协议无关。

刻意不校验 overallFrameIdentifier 与 frameIdentifier 的关系（2026 Pack 语义 UNVERIFIED）。
首帧无历史 → 跳过跨帧检查，仅初始化状态；会话切换 → 报 INFO 并重置状态。
"""

from __future__ import annotations

from typing import Optional

from store.schemas import PacketHeader

from validate.report import Severity, ValidationIssue, ValidationReport
from validate.rules import FrameContext, ValidationChain


class FrameValidator:
    """无状态规则链 + 跨帧顺序检查的组合校验器（有状态，须跨帧复用同一实例）。"""

    def __init__(self, chain: ValidationChain) -> None:
        self._chain = chain
        self._last_session_uid: Optional[int] = None
        self._last_frame_identifier: Optional[int] = None
        self._last_session_time: Optional[float] = None

    def validate(self, data: bytes, header: PacketHeader | None) -> ValidationReport:
        report = self._chain.validate(FrameContext(data, header))
        if header is None:
            return report
        sequence = self._sequence_checks(header)
        self._update_state(header)
        return report.merged(ValidationReport(tuple(sequence)))

    def _sequence_checks(self, header: PacketHeader) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        # 首帧：无历史，仅初始化（调用方随后 _update_state）
        if self._last_session_uid is None:
            return issues

        # 会话边界：sessionUID 变 → 报 INFO，不做顺序比较（新会话 frame/time 会归零）
        if header.m_sessionUID != self._last_session_uid:
            issues.append(
                ValidationIssue(
                    "session_changed",
                    Severity.INFO,
                    f"sessionUID {self._last_session_uid} -> {header.m_sessionUID}",
                )
            )
            return issues

        # 同会话内：帧序 / 重复 / sessionTime 回退
        if header.m_frameIdentifier < self._last_frame_identifier:
            issues.append(
                ValidationIssue(
                    "frame_identifier_regression",
                    Severity.WARN,
                    f"frameIdentifier {header.m_frameIdentifier} < {self._last_frame_identifier}",
                )
            )
        elif header.m_frameIdentifier == self._last_frame_identifier:
            issues.append(
                ValidationIssue(
                    "duplicate_frame",
                    Severity.WARN,
                    f"frameIdentifier {header.m_frameIdentifier} 重复投递",
                )
            )

        if header.m_sessionTime < self._last_session_time:
            issues.append(
                ValidationIssue(
                    "session_time_regression",
                    Severity.WARN,
                    f"sessionTime {header.m_sessionTime} < {self._last_session_time}",
                )
            )

        return issues

    def _update_state(self, header: PacketHeader) -> None:
        self._last_session_uid = header.m_sessionUID
        self._last_frame_identifier = header.m_frameIdentifier
        self._last_session_time = header.m_sessionTime
