"""L5 接真实 LLM（Claude）：ClaudeRaceEngineer —— 多轮 tool-use 循环。

约束（docs/architecture.md §1）：
  - AI 层永不直接碰 UDP、永不自己算数，只通过 Tool 层读数据。
  - 每个 Tool 返回的 ToolResult 带 5 字段数据信封（source_level / source / timestamp /
    unit / confidence），回传给模型时原样保留，模型据此区分实测（RAW/DERIVED）与
    推测（MODEL/HYPOTHESIS）。

本模块引入具体模型 SDK（Anthropic `anthropic`）。`RaceEngineer`（race_engineer.py）仍是
LLM-agnostic 的薄调度器；本类只负责「把用户问题交给 LLM、执行 LLM 选的 tool、把结果带
信封回传、直到 LLM 不再要 tool」这一循环，不读数据、不算数。

选型：默认 `claude-opus-5`（adaptive thinking）。模型 / 客户端 / thinking / max_tokens /
max_turns 均可经构造参数覆盖；`client=None` 时惰性构造 `anthropic.Anthropic()`（从环境变量
读凭据），注入 fake client 即可离线单测，不触发 SDK import。
"""

from __future__ import annotations

import json
from typing import Any

from agent.race_engineer import RaceEngineer
from tools.registry import ToolResult


SYSTEM_PROMPT = (
    "你是 F1 25 赛程工程师 AI。你只通过一组只读工具读取遥测数据，绝不直接接触 UDP、"
    "也绝不自行计算。\n"
    "每个工具返回都带数据信封：source_level（RAW / DERIVED / GAME_DATA / VALIDATED / "
    "MODEL / HYPOTHESIS）与 confidence（HIGH / MEDIUM / LOW）。回答时必须据此区分：\n"
    "  - RAW / DERIVED：实测数据或由实测经确定性计算，可当作事实陈述；\n"
    "  - GAME_DATA：可靠的游戏规则 / 参数；\n"
    "  - VALIDATED：用户实测验证过；\n"
    "  - MODEL / HYPOTHESIS：推断或假设，必须明说「这是推测 / 假设」。\n"
    "铁律：没有数据就没有结论（NO DATA → NO FACT）。缺数据时明说缺数据，绝不编造。\n"
    "推荐 setup 时调用 recommend_setup：params 里每个非 None 参数都必须有 rationale 覆盖，"
    "每条 rationale 必须带 evidence（tool/source_level/confidence 与真实读到的工具结果信封一致），"
    "禁止无据给数字。"
)


class ClaudeRaceEngineer:
    """通过 Claude Messages API 跑多轮 tool-use 循环的赛程工程师。"""

    def __init__(
        self,
        store,
        client: Any = None,
        model: str = "claude-opus-5",
        system: str | None = None,
        thinking: dict | None = None,
        max_tokens: int = 16000,
        max_turns: int = 10,
    ) -> None:
        self.engine = RaceEngineer(store)
        self.model = model
        self.system = system if system is not None else SYSTEM_PROMPT
        # None 表示「不显式传 thinking」，回到模型默认；默认走 adaptive。
        self.thinking = thinking if thinking is not None else {"type": "adaptive"}
        self.max_tokens = max_tokens
        self.max_turns = max_turns
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client = client

    def ask(
        self,
        question: str,
        history: list[dict] | None = None,
        max_turns: int | None = None,
    ) -> tuple[str, list[dict]]:
        """向 LLM 提问，返回 `(最终回答文本, 完整消息历史)`。

        `history` 传入时续接既有对话（多轮）；返回值中的 `messages` 可直接作为下一次
        `ask` 的 `history` 入参。循环：`while stop_reason == "tool_use"`，执行每个
        tool_use 并把带 5 字段信封的结果回传，直到 `end_turn`（或达 max_turns）。
        """
        messages = list(history) if history else []
        messages.append({"role": "user", "content": question})
        turns = max_turns if max_turns is not None else self.max_turns
        tools = self.engine.anthropic_tools()

        response = None
        for _ in range(turns):
            kwargs: dict[str, Any] = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "system": self.system,
                "tools": tools,
                "messages": messages,
            }
            if self.thinking is not None:
                kwargs["thinking"] = self.thinking
            response = self.client.messages.create(**kwargs)

            # 每轮都先把 assistant 的完整 content 写回历史（含最终文本轮），续聊时
            # 模型才能记得自己说过什么；只有 tool_use 轮才再补一条 tool_result。
            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                break

            results = [
                self._tool_result(block)
                for block in response.content
                if block.type == "tool_use"
            ]
            messages.append({"role": "user", "content": results})

        if response is None:
            return "", messages

        text = "\n".join(b.text for b in response.content if b.type == "text").strip()
        if response.stop_reason == "tool_use":
            text = (text + "\n\n[达到 max_turns，模型仍请求更多工具，已截断]").strip()
        elif response.stop_reason == "max_tokens":
            text = (text + "\n\n[回答被 max_tokens 截断]").strip()
        elif response.stop_reason == "refusal":
            text = text or "[模型拒绝回答]"
        return text, messages

    def _tool_result(self, block) -> dict:
        """执行一个 tool_use 块，把 ToolResult 的 5 字段信封原样回传；失败标 is_error。"""
        try:
            result: ToolResult = self.engine.call(block.name, **dict(block.input or {}))
            content = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
            return {"type": "tool_result", "tool_use_id": block.id, "content": content}
        except Exception as exc:  # noqa: BLE001 — 工具错误需诚实回传，不吞掉
            content = json.dumps(
                {"tool": block.name, "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
            )
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
                "is_error": True,
            }
