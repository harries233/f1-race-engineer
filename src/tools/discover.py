"""Tool：list_sessions —— 发现已入库会话（store 元数据）。

让 AI 先知道库里有哪些会话（session_uid + 帧数 + 首末 sessionTime），再决定查哪个
会话的遥测/圈速。session_uid 直接来自原始帧 header（RAW）。
"""

from __future__ import annotations

from store.schemas import Confidence, SourceLevel, now_utc
from tools.registry import Tool, ToolResult


def list_sessions(store) -> Tool:
    """构造 list_sessions Tool（依赖注入 store 只读句柄）。"""

    def handler():
        return ToolResult(
            source_level=SourceLevel.RAW,
            source="udp:raw",
            timestamp=now_utc(),
            unit="session",
            confidence=Confidence.HIGH,
            data=store.sessions(),
            notes=["session_uid 直接来自原始帧 header；first/last_session_time 为帧内 sessionTime 秒"],
        )

    return Tool(
        name="list_sessions",
        description="列出库中已接收到的会话清单（session_uid + 帧数 + 首末 sessionTime），用于发现与选择会话。",
        parameters={"type": "object", "properties": {}},
        handler=handler,
    )
