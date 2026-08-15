"""Tool：recommend_setup / list_recommendations —— 结构化 Setup 推荐（PHASE 12）。

`recommend_setup` 是 L5 AI「推荐 setup」的落点：AI 综合只读 Tool（get_lap/get_sector/
get_corner/compare/validate_setup）读到的数据，产出一条 `SetupRecommendation`
（SetupParams + rationale + evidence），经 `validate_recommendation` 诚实性校验后落库。

诚实性不变量（analysis/recommend.py）：推荐的每个非 None 参数都必须有 rationale 覆盖，
且每条 rationale 必须带来自真实 ToolResult 的 evidence（tool/source_level/confidence 一致），
否则**不落库**，把违规清单回传给 LLM 补齐。推荐整体 source_level=HYPOTHESIS（待验证），
confidence = 所有 evidence 的最弱置信度（weakest-link，不信任模型自评）。
"""

from __future__ import annotations

from analysis.recommend import validate_recommendation, weakest_confidence
from store.schemas import (
    Confidence,
    SetupParams,
    SetupRationale,
    SetupRecommendation,
    SourceLevel,
    ValidationStatus,
    now_utc,
)
from tools.registry import Tool, ToolResult


def recommend_setup(store) -> Tool:
    """构造 recommend_setup Tool（依赖注入 ExperimentStore，需有 save_recommendation 方法）。"""

    def handler(
        recommendation_id: str,
        track_id: str,
        setup_version: str,
        summary: str,
        params: dict,
        rationale: list[dict],
        session_uid=None,
    ) -> ToolResult:
        setup_params = SetupParams(**params)
        rationales = [SetupRationale(**r) for r in rationale]

        violations = validate_recommendation(setup_params, rationales)
        if violations:
            return ToolResult(
                source_level=SourceLevel.HYPOTHESIS,
                source="ai:setup_recommendation",
                timestamp=now_utc(),
                unit="setup",
                confidence=Confidence.LOW,
                data=None,
                notes=["推荐未落库：诚实性校验未通过，请补 rationale/evidence 后重试"]
                + violations,
            )

        confidence = weakest_confidence(
            ev.confidence for r in rationales for ev in r.evidence
        )
        recommendation = SetupRecommendation(
            source_level=SourceLevel.HYPOTHESIS,
            source="ai:setup_recommendation",
            timestamp=now_utc(),
            unit="setup",
            confidence=confidence,
            recommendation_id=recommendation_id,
            track_id=track_id,
            session_uid=session_uid,
            setup_version=setup_version,
            summary=summary,
            params=setup_params,
            rationale=rationales,
            status=ValidationStatus.PREDICTED,
        )
        store.save_recommendation(recommendation)
        return ToolResult(
            source_level=SourceLevel.HYPOTHESIS,
            source="ai:setup_recommendation",
            timestamp=recommendation.timestamp,
            unit="setup",
            confidence=confidence,
            data=recommendation.model_dump(),
            notes=["推荐已落库，status=PREDICTED，待 A-B 验证"],
        )

    return Tool(
        name="recommend_setup",
        description=(
            "产出一条结构化 Setup 推荐并落库（HYPOTHESIS，待验证）。诚实规则：params 里每个"
            "非 None 参数都必须在 rationale 里有对应一条（field==字段名 或 'all'），且该条必须"
            "带 evidence（tool/source_level/confidence 与真实读到的工具结果信封一致）；无据给数字"
            "会被拒绝。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "recommendation_id": {"type": "string", "description": "推荐唯一标识"},
                "track_id": {"type": "string", "description": "赛道标识"},
                "setup_version": {
                    "type": "string",
                    "description": "目标版本号（后续可被 save_setup/validate_setup 复用）",
                },
                "summary": {"type": "string", "description": "推荐一句话总结"},
                "params": {
                    "type": "object",
                    "description": "SetupParams 子集（只填建议改动的字段，None/缺失=保持现状；字段名见 schemas.py）",
                },
                "rationale": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string", "description": "SetupParams 字段名；'all'=整体策略"},
                            "change": {"type": "string", "description": "建议动作（如 '+2' / '软一档' / '保持'）"},
                            "reason": {"type": "string", "description": "为什么（引用 evidence）"},
                            "evidence": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "tool": {"type": "string", "description": "证据来源只读 Tool 名"},
                                        "source_level": {"type": "string", "description": "该证据来源等级（RAW/DERIVED/GAME_DATA…）"},
                                        "confidence": {"type": "string", "description": "该证据置信度（HIGH/MEDIUM/LOW）"},
                                        "summary": {"type": "string", "description": "证据要点"},
                                    },
                                    "required": ["tool", "source_level", "confidence", "summary"],
                                },
                            },
                        },
                        "required": ["field", "change", "reason", "evidence"],
                    },
                    "description": "每条改动（或整体策略）的理由 + 证据清单",
                },
                "session_uid": {"type": "integer", "description": "会话 UID；可选"},
            },
            "required": [
                "recommendation_id",
                "track_id",
                "setup_version",
                "summary",
                "params",
                "rationale",
            ],
        },
        handler=handler,
    )


def list_recommendations(store) -> Tool:
    """构造 list_recommendations Tool（依赖注入 ExperimentStore，需有 list_recommendations 方法）。"""

    def handler(status: str | None = None) -> ToolResult:
        recs = store.list_recommendations(status=status)
        return ToolResult(
            source_level=SourceLevel.HYPOTHESIS,
            source="ai:setup_recommendation",
            timestamp=now_utc(),
            unit="setup",
            confidence=Confidence.HIGH,
            data=[r.model_dump() for r in recs],
            notes=["列表内容均为 HYPOTHESIS（AI 推断，待 A-B 验证）；列表本身如实返回已存记录"],
        )

    return Tool(
        name="list_recommendations",
        description="列出已落库的 Setup 推荐（可选按 status 过滤：PREDICTED/VALIDATED/NOT_VALIDATED 等）。",
        parameters={
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "可选：按 ValidationStatus 过滤"},
            },
        },
        handler=handler,
    )
