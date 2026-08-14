"""Tool：compare —— 两组完赛圈（BASELINE vs TEST）圈速对比（DERIVED）。

按圈号把某车的完赛圈分成两组，调 L4 `analysis.compare.compare_laps` 算确定性 delta。
AI 层不自己算数，只读 L4 结果。delta 单位：秒，负值 = test 更快。
"""

from __future__ import annotations

from analysis.compare import compare_laps
from store.schemas import Confidence, SourceLevel, now_utc
from tools.lap import completed_laps
from tools.registry import Tool, ToolResult


def compare(store) -> Tool:
    """构造 compare Tool（依赖注入 store 只读句柄）。"""

    def handler(
        car_index: int,
        baseline_laps: list[int],
        test_laps: list[int],
        session_uid=None,
    ) -> ToolResult:
        records = completed_laps(store, car_index, session_uid)
        if not records:
            return ToolResult(
                source_level=SourceLevel.DERIVED,
                source="calc:compare",
                timestamp=now_utc(),
                unit="s",
                confidence=Confidence.HIGH,
                data=None,
                notes=[f"车辆 {car_index} 无完赛圈数据"],
            )

        baseline_set = set(baseline_laps)
        test_set = set(test_laps)
        baseline = [r for r in records if r.lap_number in baseline_set]
        test = [r for r in records if r.lap_number in test_set]

        result = compare_laps(baseline, test)
        return ToolResult(
            source_level=SourceLevel.DERIVED,
            source="calc:compare",
            timestamp=records[0].timestamp,
            unit="s",
            confidence=Confidence.HIGH,
            data=result.as_dict(),
            notes=list(result.notes),
        )

    return Tool(
        name="compare",
        description="对比两组完赛圈的圈速与分段时间（BASELINE vs TEST），返回 delta 指标（负=test 更快）。",
        parameters={
            "type": "object",
            "properties": {
                "car_index": {"type": "integer", "description": "车辆索引 0–23"},
                "baseline_laps": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "BASELINE 组的圈号列表",
                },
                "test_laps": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "TEST 组的圈号列表",
                },
                "session_uid": {"type": "integer", "description": "会话 UID；缺省取最新"},
            },
            "required": ["car_index", "baseline_laps", "test_laps"],
        },
        handler=handler,
    )
