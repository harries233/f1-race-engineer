"""Tool：validate_setup —— 创建并运行一次 Setup A-B 实验（DERIVED）。

流程：按圈号取 BASELINE/TEST 两组完赛圈 → L4 `evaluate_experiment` 算 delta + 推导
ValidationStatus → 持久化到 ExperimentStore → 返回最终 Experiment。

这是 L5 AI「推荐 setup 后验证」的落点：AI 推荐 setup → 用户跑圈 → 本 Tool 判定该
setup 是否更快。判定只基于圈速，不做因果归因（混杂因素见 test_conditions）。
"""

from __future__ import annotations

from analysis.experiment import evaluate_experiment
from store.schemas import (
    Confidence,
    Experiment,
    SourceLevel,
    TestConditions,
    ValidationStatus,
    now_utc,
)
from tools.lap import completed_laps
from tools.registry import Tool, ToolResult


def validate_setup(store) -> Tool:
    """构造 validate_setup Tool（依赖注入 ExperimentStore，需有 save_experiment 方法）。"""

    def handler(
        exp_id: str,
        hypothesis: str,
        setup_baseline_version: str,
        setup_test_version: str,
        baseline_laps: list[int],
        test_laps: list[int],
        car_index: int,
        test_conditions: dict | None = None,
        session_uid=None,
    ) -> ToolResult:
        records = completed_laps(store, car_index, session_uid)
        if not records:
            return ToolResult(
                source_level=SourceLevel.DERIVED,
                source="calc:experiment",
                timestamp=now_utc(),
                unit="s",
                confidence=Confidence.LOW,
                data=None,
                notes=[f"车辆 {car_index} 无完赛圈数据，实验未运行"],
            )

        experiment = Experiment(
            source_level=SourceLevel.DERIVED,
            source="calc:experiment",
            timestamp=now_utc(),
            unit="s",
            confidence=Confidence.LOW,
            exp_id=exp_id,
            hypothesis=hypothesis,
            setup_baseline_version=setup_baseline_version,
            setup_test_version=setup_test_version,
            status=ValidationStatus.PREDICTED,
            test_conditions=TestConditions(**(test_conditions or {})),
            baseline_laps=list(baseline_laps),
            test_laps=list(test_laps),
        )

        baseline_set = set(baseline_laps)
        test_set = set(test_laps)
        baseline = [r for r in records if r.lap_number in baseline_set]
        test = [r for r in records if r.lap_number in test_set]

        result = evaluate_experiment(experiment, baseline, test)
        store.save_experiment(result)

        return ToolResult(
            source_level=SourceLevel.DERIVED,
            source="calc:experiment",
            timestamp=result.timestamp,
            unit="s",
            confidence=result.confidence,
            data=result.model_dump(),
            notes=[
                "判定仅基于圈速，未做因果归因；混杂因素见 test_conditions",
                f"baseline_n={len(baseline)} test_n={len(test)}",
            ],
        )

    return Tool(
        name="validate_setup",
        description="创建并运行一次 Setup A-B 实验：对比 BASELINE/TEST 圈速，判定 setup 是否更快并持久化。",
        parameters={
            "type": "object",
            "properties": {
                "exp_id": {"type": "string", "description": "实验唯一标识"},
                "hypothesis": {"type": "string", "description": "实验假设，如「前翼+2 提升 S2 出弯」"},
                "setup_baseline_version": {"type": "string", "description": "BASELINE setup 版本"},
                "setup_test_version": {"type": "string", "description": "TEST setup 版本"},
                "baseline_laps": {"type": "array", "items": {"type": "integer"}, "description": "BASELINE 圈号"},
                "test_laps": {"type": "array", "items": {"type": "integer"}, "description": "TEST 圈号"},
                "car_index": {"type": "integer", "description": "车辆索引 0–23"},
                "test_conditions": {
                    "type": "object",
                    "description": "测试条件（fuel/tyre_compound/weather/track_temp/ers/drs 等，可选）",
                },
                "session_uid": {"type": "integer", "description": "会话 UID；缺省取最新"},
            },
            "required": [
                "exp_id",
                "hypothesis",
                "setup_baseline_version",
                "setup_test_version",
                "baseline_laps",
                "test_laps",
                "car_index",
            ],
        },
        handler=handler,
    )
