"""L4→L5 Tool 层（PHASE 6/7/8/9/12）：把 L3/L4 暴露成 AI 可调用的 Tool。

每个 Tool 返回 `ToolResult`（强制 5 字段数据信封）。AI 层只通过 ToolRegistry 读数据，
永不直接碰 UDP、也不自己算数（docs/architecture.md §1）。

`build_registry(store)` 装配全部 Tool。只读 Tool（get_session/get_telemetry/get_lap/
list_sessions/compare/get_sector/get_corner）只需 store 有 query()/sessions()；写 Tool
（save_setup/list_setups/validate_setup/recommend_setup/list_recommendations）需 store 提供
对应方法（见 store/experiment_store.py 的 ExperimentStore），缺方法时在调用期才报错
（构建期不触发 handler）。
"""

from tools.compare import compare
from tools.corner import get_corner
from tools.discover import list_sessions
from tools.experiment import list_experiments, validate_setup
from tools.lap import get_lap
from tools.recommend import list_recommendations, recommend_setup
from tools.registry import Tool, ToolRegistry, ToolResult
from tools.sector import get_sector
from tools.session import get_session
from tools.setup import list_setups, save_setup
from tools.telemetry import get_telemetry


def build_registry(store) -> ToolRegistry:
    """把已实现的所有 Tool 装配进一个注册表（依赖注入 store 句柄）。"""
    return ToolRegistry(
        [
            get_session(store),
            get_telemetry(store),
            get_lap(store),
            get_sector(store),
            get_corner(store),
            list_sessions(store),
            compare(store),
            save_setup(store),
            list_setups(store),
            validate_setup(store),
            recommend_setup(store),
            list_recommendations(store),
            list_experiments(store),
        ]
    )


__all__ = [
    "Tool",
    "ToolRegistry",
    "ToolResult",
    "get_session",
    "get_telemetry",
    "get_lap",
    "get_sector",
    "get_corner",
    "list_sessions",
    "compare",
    "save_setup",
    "list_setups",
    "validate_setup",
    "recommend_setup",
    "list_recommendations",
    "list_experiments",
    "build_registry",
]
