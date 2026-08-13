"""校验框架：规则签名 + 上下文 + 链（协议无关）。

ValidationRule 是 PHASE 3 字段级 validator 的扩展点：payload 字段解析落地后，
实现同一签名（FrameContext → list[ValidationIssue]）即可接入链，无需改框架。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from store.schemas import PacketHeader

from validate.report import ValidationIssue, ValidationReport


@dataclass(frozen=True)
class FrameContext:
    """单帧校验上下文：原始 datagram + 已解析 header（datagram < 29 时 header 为 None）。"""

    data: bytes
    header: PacketHeader | None


# 一条校验规则：对单帧返回 0+ 条问题。规则应互相独立、无状态。
ValidationRule = Callable[[FrameContext], list[ValidationIssue]]


class ValidationChain:
    """按序跑一组规则，汇总所有 issues 成一份报告。"""

    def __init__(self, rules: list[ValidationRule]) -> None:
        self._rules = rules

    def validate(self, ctx: FrameContext) -> ValidationReport:
        issues: list[ValidationIssue] = []
        for rule in self._rules:
            issues.extend(rule(ctx))
        return ValidationReport(tuple(issues))
