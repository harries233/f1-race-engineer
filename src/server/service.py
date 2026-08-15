"""服务层装配（PHASE 14）：Service —— 把 receiver + store + RaceEngineer 组装成常驻服务。

职责（只接线，不算数）：
  - 持有 store（ExperimentStore）、engine（RaceEngineer，Tool 派发）、claude
    （ClaudeRaceEngineer，AI 对话）、manager（ConnectionManager，WS 广播）。
  - `ingest(packet)`：receiver 的 on_packet 回调 —— 落库 + 提取实时事件广播。
  - `call_tool(name, **kwargs)`：薄封装 engine.call，REST 只读端点统一走这里。
  - `ask(question, ...)`：AI 对话委托 ClaudeRaceEngineer。
  - `start_receiver()/stop_receiver()`：把 UDP 接收跑在后台线程，供 FastAPI lifespan 启停。

receiver 可选：不传（或传 None）即「只读服务」，对已入库数据提供仪表盘 + AI 对话，
不启动 UDP 监听（测试 / 回放历史数据时用）。
"""

from __future__ import annotations

import threading
from typing import Any, Callable

from agent.claude import ClaudeRaceEngineer
from agent.race_engineer import RaceEngineer
from server.events import build_event
from server.ws import ConnectionManager
from store.schemas import RawPacket
from tools.registry import ToolResult


class Service:
    """常驻服务的进程内装配点。"""

    def __init__(
        self,
        store,
        *,
        receiver=None,
        claude: ClaudeRaceEngineer | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.store = store
        self.engine = RaceEngineer(store)
        self.claude = claude if claude is not None else ClaudeRaceEngineer(store)
        self.manager = ConnectionManager()
        self.receiver = receiver
        if receiver is not None:
            receiver.on_packet = self.ingest
        # on_event 可注入（测试用 spy 捕获广播，避开异步）；缺省推给 WS 连接。
        self._on_event = on_event if on_event is not None else self.manager.publish
        self._receiver_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # 数据链路
    # ------------------------------------------------------------------

    def ingest(self, packet: RawPacket) -> int:
        """receiver 回调：落库一帧 + 广播实时事件，返回 raw_packets 行 id。"""
        raw_id = self.store.save(packet)
        event = build_event(packet)
        if event is not None:
            self._on_event(event)
        return raw_id

    def call_tool(self, name: str, **kwargs) -> ToolResult:
        """REST 只读端点的统一入口：按名派发 Tool，保留 5 字段信封。"""
        return self.engine.call(name, **kwargs)

    def ask(
        self,
        question: str,
        history: list[dict] | None = None,
        max_turns: int | None = None,
    ) -> tuple[str, list[dict]]:
        """AI 对话：委托 ClaudeRaceEngineer 跑多轮 tool-use 循环。"""
        return self.claude.ask(question, history=history, max_turns=max_turns)

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start_receiver(self) -> None:
        """把 UDP 接收跑在后台守护线程（仅当配置了 receiver）。"""
        if self.receiver is None or self._receiver_thread is not None:
            return
        self._receiver_thread = threading.Thread(
            target=self.receiver.serve_forever, daemon=True, name="udp-receiver"
        )
        self._receiver_thread.start()

    def stop_receiver(self) -> None:
        """关闭 UDP socket 使 serve_forever 干净退出。"""
        if self.receiver is not None:
            self.receiver.close()
