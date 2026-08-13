"""校验层报告结构（协议无关）。

定义校验问题的严重级别（ERROR/WARN/INFO）、单条问题、以及整帧的校验报告。
- ERROR：帧无效 → 顶层 status = VALIDATION_FAILED（上层保留原始 datagram，不丢弃）。
- WARN/INFO：异常/备注，不翻 status，帧仍 VALID。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from store.schemas import PacketValidationStatus


class Severity(str, Enum):
    ERROR = "ERROR"   # 帧无效
    WARN = "WARN"     # 异常，帧保留
    INFO = "INFO"     # 备注（如会话边界）


@dataclass(frozen=True)
class ValidationIssue:
    """单条校验问题。code 是稳定机器码，供下游（PHASE 3 入库/统计）引用。"""

    code: str
    severity: Severity
    message: str


@dataclass(frozen=True)
class ValidationReport:
    """整帧校验报告。status 由 issues 派生：任一 ERROR → VALIDATION_FAILED。"""

    issues: tuple[ValidationIssue, ...] = ()

    @property
    def status(self) -> PacketValidationStatus:
        if any(i.severity is Severity.ERROR for i in self.issues):
            return PacketValidationStatus.VALIDATION_FAILED
        return PacketValidationStatus.VALID

    def merged(self, other: "ValidationReport") -> "ValidationReport":
        """合并两份报告（如无状态规则链 + 跨帧顺序检查）。"""
        return ValidationReport(self.issues + other.issues)
