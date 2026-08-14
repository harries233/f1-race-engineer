"""Tool：save_setup / list_setups —— 注册与发现 Setup 快照（GAME_DATA）。

Setup 参数清单（SetupParams）来自游戏 Car Setup 页面，由 AI 推荐、用户确认后落库，
供 A-B 实验（validate_setup）引用为 BASELINE/TEST 版本。source_level=GAME_DATA：
数值是精确的游戏设置值，非模型产出。
"""

from __future__ import annotations

from store.schemas import Confidence, SetupParams, SetupSnapshot, SourceLevel, now_utc
from tools.registry import Tool, ToolResult


def save_setup(store) -> Tool:
    """构造 save_setup Tool（依赖注入 ExperimentStore，需有 save_setup 方法）。"""

    def handler(setup_version: str, track_id: str, label: str, params: dict) -> ToolResult:
        # 参数名用 label（而非 name）：ToolRegistry.call(name, ...) 已占用 name 作工具名。
        snapshot = SetupSnapshot(
            source_level=SourceLevel.GAME_DATA,
            source="game:car_setup",
            timestamp=now_utc(),
            unit="setup",
            confidence=Confidence.HIGH,
            setup_version=setup_version,
            track_id=track_id,
            name=label,
            params=SetupParams(**params),
        )
        store.save_setup(snapshot)
        return ToolResult(
            source_level=SourceLevel.GAME_DATA,
            source="game:car_setup",
            timestamp=snapshot.timestamp,
            unit="setup",
            confidence=Confidence.HIGH,
            data=snapshot.model_dump(),
        )

    return Tool(
        name="save_setup",
        description="注册一次 Setup 快照（版本化），供 A-B 实验引用为 BASELINE/TEST 版本。",
        parameters={
            "type": "object",
            "properties": {
                "setup_version": {
                    "type": "string",
                    "description": "版本号（如 'v1' / 'baseline-a'），实验引用此标识",
                },
                "track_id": {"type": "string", "description": "赛道标识"},
                "label": {"type": "string", "description": "快照人类可读名称"},
                "params": {
                    "type": "object",
                    "description": "SetupParams 字段子集（前翼/后翼/胎压/悬挂等，单位见 schemas.py）",
                },
            },
            "required": ["setup_version", "track_id", "label", "params"],
        },
        handler=handler,
    )


def list_setups(store) -> Tool:
    """构造 list_setups Tool（依赖注入 ExperimentStore，需有 list_setups 方法）。"""

    def handler() -> ToolResult:
        snapshots = store.list_setups()
        return ToolResult(
            source_level=SourceLevel.GAME_DATA,
            source="game:car_setup",
            timestamp=now_utc(),
            unit="setup",
            confidence=Confidence.HIGH,
            data=[s.model_dump() for s in snapshots],
        )

    return Tool(
        name="list_setups",
        description="列出已注册的 Setup 快照（setup_version + 参数），用于选择 A-B 实验的 BASELINE/TEST。",
        parameters={"type": "object", "properties": {}},
        handler=handler,
    )
