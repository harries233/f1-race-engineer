"""WebSocket 连接管理 + 跨线程安全广播（PHASE 14）。

UDP 接收线程（同步 `receiver.serve_forever`）产生实时事件，需要推给各 WebSocket 连接
（异步，跑在 FastAPI 的事件循环里）。两者跨线程：`ConnectionManager` 在首个连接建立时
捕获事件循环，之后 `publish()`（接收线程调用）用 `asyncio.run_coroutine_threadsafe`
把广播协程投递回该循环执行。

发送失败（连接已断）只丢弃该连接，不拖垮整轮广播 —— 接收链路与推送解耦。
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """WebSocket 连接的注册/注销 + 线程安全广播。"""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        self._loop = asyncio.get_running_loop()

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    def count(self) -> int:
        return len(self._connections)

    def publish(self, message: dict[str, Any]) -> None:
        """线程安全广播：把消息投递到每个连接所在的事件循环发送。"""
        if self._loop is None or not self._connections:
            return
        for websocket in list(self._connections):
            asyncio.run_coroutine_threadsafe(self._send(websocket, message), self._loop)

    async def _send(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        try:
            await websocket.send_json(message)
        except Exception:  # noqa: BLE001 — 连接已断/发送失败，丢弃该连接，不打断广播
            self._connections.discard(websocket)
