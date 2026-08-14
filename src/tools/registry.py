"""Tool 层基础：Tool 抽象 + 注册表 + ToolResult（PHASE 6）。

这是 L4/L3 暴露给 L5 AI 的唯一接口。AI 层只认识本模块的 `Tool` / `ToolRegistry` /
`ToolResult`，永不直接碰 UDP、也不自己算数（docs/architecture.md §1）。

设计：
  - Tool：具名、带人类可读 description 与 JSON Schema 参数、一个 handler 可调用。
    handler 签名 `(**params) -> ToolResult`。
  - ToolRegistry：按名注册/查找/派发；`function_schemas()` 输出 OpenAI
    function-calling 形状的 JSON，供上层 LLM 选 Tool。
  - ToolResult：每个 Tool 的返回值，强制带 5 字段数据信封（source_level / source /
    timestamp / unit / confidence），`data` 承载实际载荷，`notes` 承载诚实声明
    （如「速度点待 PHASE 8/9」）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from pydantic import BaseModel, Field

from store.schemas import Confidence, SourceLevel


class ToolResult(BaseModel):
    """单个 Tool 的返回值：强制 5 字段信封 + 实际载荷 + 诚实声明。"""

    source_level: SourceLevel
    source: str
    timestamp: str
    unit: str
    confidence: Confidence
    data: Any = None
    notes: list[str] = Field(default_factory=list)


ToolHandler = Callable[..., ToolResult]


@dataclass
class Tool:
    """一个可被 AI 调用的只读工具。parameters 是 JSON Schema（type=object）。"""

    name: str
    description: str
    parameters: dict
    handler: ToolHandler


class ToolRegistry:
    """按名注册 / 查找 / 派发 Tool，并导出 function-calling Schema。"""

    def __init__(self, tools: Iterable[Tool] = ()) -> None:
        self._by_name: dict[str, Tool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        self._by_name[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._by_name.get(name)

    def names(self) -> list[str]:
        return list(self._by_name.keys())

    def tools(self) -> list[Tool]:
        return list(self._by_name.values())

    def call(self, name: str, **kwargs) -> ToolResult:
        """按名派发单个 tool call；未知名抛 KeyError。"""
        tool = self._by_name.get(name)
        if tool is None:
            raise KeyError(f"unknown tool: {name}")
        return tool.handler(**kwargs)

    def function_schemas(self) -> list[dict]:
        """OpenAI function-calling 形状的工具清单，供上层 LLM 选 Tool。"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._by_name.values()
        ]

    def anthropic_tools(self) -> list[dict]:
        """Anthropic Messages API 的 tool 形状（name/description/input_schema）。"""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in self._by_name.values()
        ]
