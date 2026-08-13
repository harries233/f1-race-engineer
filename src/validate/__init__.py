"""L2 校验层（协议无关框架）。

- report.py：Severity / ValidationIssue / ValidationReport
- rules.py：ValidationRule（Callable 签名）/ FrameContext / ValidationChain
- frame.py：FrameValidator（跨帧顺序状态机）

具体 header 规则（packetFormat==2026 等）在 protocol/f1_25_2026/validate.py，
未来 F1_25_BASE 可加自己的 validate.py 复用本框架。
"""

from validate.report import Severity, ValidationIssue, ValidationReport
from validate.rules import FrameContext, ValidationChain, ValidationRule
from validate.frame import FrameValidator

__all__ = [
    "Severity",
    "ValidationIssue",
    "ValidationReport",
    "FrameContext",
    "ValidationRule",
    "ValidationChain",
    "FrameValidator",
]
