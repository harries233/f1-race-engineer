"""L5 AI 接入骨架（PHASE 7）：RaceEngineer —— 通过 Tool 层读数据的薄调度器。

约束（docs/architecture.md §1）：
  - AI 层永不直接碰 UDP、永不自己算数，只能调 Tool 层。
  - 每个 Tool 返回值带 source_level 信封。

本层是 LLM-agnostic 的调度骨架：持有 ToolRegistry，按名+参数 dispatch 单个 tool call，
并输出 function-calling JSON Schema 供上层 LLM 选 Tool。真正的 LLM 多轮循环 / 提示词
选型（引入具体模型 SDK）后续再接入，本 phase 不引入模型依赖。
"""

from __future__ import annotations

from tools import build_registry
from tools.registry import ToolRegistry, ToolResult


class RaceEngineer:
    """L5 AI Race Engineer 的确定性骨架。

    用法（未来接 LLM 时）：
        engineer = RaceEngineer(store)
        schemas = engineer.function_schemas()   # 喂给 LLM 选 Tool
        result = engineer.call("get_lap", car_index=0)   # 执行选中的 Tool
    """

    def __init__(self, store) -> None:
        self.registry: ToolRegistry = build_registry(store)

    def function_schemas(self) -> list[dict]:
        """OpenAI function-calling 形状的工具清单。"""
        return self.registry.function_schemas()

    def tool_names(self) -> list[str]:
        return self.registry.names()

    def call(self, name: str, **kwargs) -> ToolResult:
        """按名派发单个 tool call，返回带 source_level 信封的 ToolResult。"""
        return self.registry.call(name, **kwargs)
