"""L4→L5 Tool 层（PHASE 6）：把 L3/L4 暴露成 AI 可调用的 Tool。

每个 Tool 返回 `ToolResult`（强制 5 字段数据信封）。AI 层只通过 ToolRegistry 读数据，
永不直接碰 UDP、也不自己算数（docs/architecture.md §1）。
"""

from tools.discover import list_sessions
from tools.lap import get_lap
from tools.registry import Tool, ToolRegistry, ToolResult
from tools.session import get_session
from tools.telemetry import get_telemetry


def build_registry(store) -> ToolRegistry:
    """把已实现的所有 Tool 装配进一个注册表（依赖注入 store 只读句柄）。"""
    return ToolRegistry(
        [
            get_session(store),
            get_telemetry(store),
            get_lap(store),
            list_sessions(store),
        ]
    )


__all__ = [
    "Tool",
    "ToolRegistry",
    "ToolResult",
    "get_session",
    "get_telemetry",
    "get_lap",
    "list_sessions",
    "build_registry",
]
