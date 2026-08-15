"""Unit tests：L5 RaceEngineer 调度骨架（PHASE 7）+ ClaudeRaceEngineer 多轮循环。"""

from agent.claude import ClaudeRaceEngineer
from agent.race_engineer import RaceEngineer
from ingest.receiver import TelemetryReceiver
from mock.factory import build_session_datagram
from store.schemas import SourceLevel
from store.structured_store import StructuredPacketStore


def _make_packet(datagram):
    receiver = TelemetryReceiver(port=12345)
    return receiver._to_packet(datagram, ("192.168.1.10", 51234))


def test_race_engineer_dispatches_tool(tmp_path):
    store = StructuredPacketStore(tmp_path / "t.sqlite3")
    store.save(_make_packet(build_session_datagram(weather=3)))

    engineer = RaceEngineer(store)
    assert "get_session" in engineer.tool_names()

    result = engineer.call("get_session")
    assert result.source_level == SourceLevel.RAW
    assert result.data["m_weather"] == 3
    store.close()


def test_race_engineer_exposes_schemas(tmp_path):
    store = StructuredPacketStore(tmp_path / "t.sqlite3")
    engineer = RaceEngineer(store)
    schemas = engineer.function_schemas()
    store.close()

    assert len(schemas) == 13
    assert all(s["type"] == "function" for s in schemas)


# --- ClaudeRaceEngineer（L5 接真实 LLM）多轮循环，用 fake client 离线测，不联网 ---


class _FakeBlock:
    def __init__(self, type_, **kw):
        self.type = type_
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content


class _FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, responses):
        self.messages = _FakeMessages(responses)


def test_claude_engine_exposes_anthropic_tools(tmp_path):
    store = StructuredPacketStore(tmp_path / "t.sqlite3")
    engine = ClaudeRaceEngineer(store, client=_FakeClient([]))
    tools = engine.engine.anthropic_tools()
    store.close()

    assert len(tools) == 13
    # Anthropic 形状：name/description/input_schema，无 OpenAI 的 type/function 包装
    assert all({"name", "description", "input_schema"} <= set(t) for t in tools)
    assert all("type" not in t for t in tools)


def test_claude_engine_multi_turn_loop(tmp_path):
    store = StructuredPacketStore(tmp_path / "t.sqlite3")
    store.save(_make_packet(build_session_datagram(weather=3)))

    resp1 = _FakeResponse(
        "tool_use",
        [_FakeBlock("tool_use", name="get_session", id="toolu_1", input={})],
    )
    resp2 = _FakeResponse(
        "end_turn", [_FakeBlock("text", text="天气是 clear（weather=3）")]
    )
    client = _FakeClient([resp1, resp2])

    engine = ClaudeRaceEngineer(store, client=client)
    answer, history = engine.ask("现在天气如何？")
    store.close()

    assert "3" in answer
    assert len(client.messages.calls) == 2

    # 第一轮：带 Anthropic tools，system prompt 含诚实约束
    first = client.messages.calls[0]
    assert any(t["name"] == "get_session" for t in first["tools"])
    assert "NO DATA" in first["system"]

    # 第二轮：把带 5 字段信封的 tool_result 回传
    second = client.messages.calls[1]
    last_user = [m for m in second["messages"] if m["role"] == "user"][-1]
    tool_result = last_user["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["tool_use_id"] == "toolu_1"
    assert "source_level" in tool_result["content"]

    # 历史可续聊：末尾是 assistant 的最终文本轮
    assert history[-1]["role"] == "assistant"


def test_claude_engine_tool_error_is_honest(tmp_path):
    store = StructuredPacketStore(tmp_path / "t.sqlite3")
    engine = ClaudeRaceEngineer(store, client=_FakeClient([]))
    block = _FakeBlock("tool_use", name="no_such_tool", id="toolu_x", input={})
    result = engine._tool_result(block)
    store.close()

    assert result["is_error"] is True
    assert "no_such_tool" in result["content"]
