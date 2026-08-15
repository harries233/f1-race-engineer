"""FastAPI 应用工厂（PHASE 14）：把 Service 暴露成 REST + WebSocket。

REST 端点薄封装 Tool 层：返回值统一是 ToolResult 的 5 字段诚实信封
（source_level/source/timestamp/unit/confidence + data + notes），服务层不新增计算、
不重写信封。AI 对话走 `Service.ask`（ClaudeRaceEngineer 多轮 tool-use 循环）。

端点到 Tool 的映射见各路由；写入类操作（save_setup / validate_setup / recommend_setup）
由 AI 在 `/api/ask` 里经 Tool 驱动，暂不单独开 REST 端点（薄客户端主要读 + 对话）。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect

from server.service import Service
from tools.registry import ToolResult


def _result(result: ToolResult) -> dict:
    """ToolResult → JSON 安全 dict（保留 5 字段信封 + data + notes）。"""
    return result.model_dump(mode="json")


def _hello(service: Service) -> dict:
    """WS 连接建立时的首条消息：当前库状态，让客户端不必空等。"""
    return {
        "type": "hello",
        "packet_count": service.store.count(),
        "sessions": service.store.sessions(),
    }


class CompareRequest(BaseModel):
    car_index: int
    baseline_laps: list[int]
    test_laps: list[int]
    session_uid: int | None = None


class AskRequest(BaseModel):
    question: str
    max_turns: int | None = None


def create_app(service: Service) -> FastAPI:
    """由 Service 装配 FastAPI 应用（REST + WS + lifespan 启停 UDP 接收）。"""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        service.start_receiver()
        yield
        service.stop_receiver()

    app = FastAPI(title="F1 25 AI Race Engineer", version="0.1.0", lifespan=lifespan)

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "packet_count": service.store.count(),
            "session_count": len(service.store.sessions()),
        }

    # ------------------------------------------------------------------
    # 只读端点（薄封装 Tool 层，保留诚实信封）
    # ------------------------------------------------------------------

    @app.get("/api/sessions")
    def sessions() -> dict:
        return _result(service.call_tool("list_sessions"))

    @app.get("/api/session")
    def session(session_uid: int | None = None) -> dict:
        return _result(service.call_tool("get_session", session_uid=session_uid))

    @app.get("/api/telemetry")
    def telemetry(car_index: int, session_uid: int | None = None) -> dict:
        return _result(
            service.call_tool("get_telemetry", car_index=car_index, session_uid=session_uid)
        )

    @app.get("/api/laps")
    def laps(
        car_index: int, lap_number: int | None = None, session_uid: int | None = None
    ) -> dict:
        return _result(
            service.call_tool(
                "get_lap",
                car_index=car_index,
                lap_number=lap_number,
                session_uid=session_uid,
            )
        )

    @app.get("/api/sectors")
    def sectors(
        car_index: int, lap_number: int | None = None, session_uid: int | None = None
    ) -> dict:
        return _result(
            service.call_tool(
                "get_sector",
                car_index=car_index,
                lap_number=lap_number,
                session_uid=session_uid,
            )
        )

    @app.get("/api/corners")
    def corners(
        car_index: int,
        lap_number: int | None = None,
        track_id: str | None = None,
        session_uid: int | None = None,
    ) -> dict:
        return _result(
            service.call_tool(
                "get_corner",
                car_index=car_index,
                lap_number=lap_number,
                track_id=track_id,
                session_uid=session_uid,
            )
        )

    @app.get("/api/setups")
    def setups() -> dict:
        return _result(service.call_tool("list_setups"))

    @app.get("/api/recommendations")
    def recommendations(status: str | None = None) -> dict:
        return _result(service.call_tool("list_recommendations", status=status))

    @app.get("/api/experiments")
    def experiments(status: str | None = None) -> dict:
        return _result(service.call_tool("list_experiments", status=status))

    # ------------------------------------------------------------------
    # 写入 / 计算端点
    # ------------------------------------------------------------------

    @app.post("/api/compare")
    def compare(body: CompareRequest) -> dict:
        return _result(
            service.call_tool(
                "compare",
                car_index=body.car_index,
                baseline_laps=body.baseline_laps,
                test_laps=body.test_laps,
                session_uid=body.session_uid,
            )
        )

    @app.post("/api/ask")
    def ask(body: AskRequest) -> dict:
        answer, _history = service.ask(body.question, max_turns=body.max_turns)
        return {"answer": answer}

    # ------------------------------------------------------------------
    # WebSocket：实时遥测推送
    # ------------------------------------------------------------------

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await service.manager.connect(websocket)
        try:
            await websocket.send_json(_hello(service))
            while True:
                await websocket.receive_text()  # 保持连接；客户端消息本 phase 忽略
        except WebSocketDisconnect:
            pass
        finally:
            service.manager.disconnect(websocket)

    return app
