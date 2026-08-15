"""HTTP/WS 服务层（PHASE 14）—— 手机薄客户端桥。

把 `receiver`（UDP）+ `store` + `RaceEngineer` 组装成常驻 FastAPI 服务，暴露 REST +
WebSocket，手机通过局域网连。服务层只做「接线」，不新增计算：REST 薄封装 Tool 层
（返回值保留 5 字段诚实信封），AI 对话委托 `ClaudeRaceEngineer`，实时遥测从已解析的
`RawPacket.structured` 提取推送。
"""

from server.app import create_app
from server.service import Service

__all__ = ["Service", "create_app"]
