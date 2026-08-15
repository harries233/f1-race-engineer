"""L5 确定性校验 —— Setup 推荐的诚实性不变量（PHASE 12）。

把「不凭空给数字」从提示词里的一句嘱咐升级成可执行、可测试的不变量：

  - 推荐的每个非 None 参数（SetupParams）都必须有至少一条 rationale 覆盖（field==字段名
    或 "all"），否则视为「无据给数字」。
  - 每条覆盖到实际改动的 rationale 必须带 ≥1 条 evidence，且 evidence.tool 必须在
    允许的只读 Tool 列表内 —— 证据只能来自 AI 实际读到的 ToolResult，不得虚构。
  - rationale 覆盖的字段在 params 里为 None → 告警（理由无对应改动）。

`validate_recommendation` 返回违规清单（空 = 通过），由 Tool 层（tools/recommend.py）
在落库前调用；有违规则不落库，让 LLM 看到缺据并补齐。
"""

from __future__ import annotations

from collections.abc import Iterable

from store.schemas import Confidence, SetupParams, SetupRationale

# 可作为证据的只读 Tool（save_setup 是写 Tool，不是证据来源）。
VALID_EVIDENCE_TOOLS = {
    "get_lap",
    "get_sector",
    "get_corner",
    "compare",
    "validate_setup",
    "get_session",
    "get_telemetry",
    "list_setups",
    "list_sessions",
}


def weakest_confidence(confidences: Iterable[Confidence]) -> Confidence:
    """求一组置信度的最弱值（weakest-link）：任一 LOW → LOW；否则任一 MEDIUM → MEDIUM；
    否则 HIGH。空集返回 LOW（无证据即最低置信）。"""
    confs = list(confidences)
    if not confs:
        return Confidence.LOW
    if Confidence.LOW in confs:
        return Confidence.LOW
    if Confidence.MEDIUM in confs:
        return Confidence.MEDIUM
    return Confidence.HIGH


def validate_recommendation(
    params: SetupParams,
    rationale: list[SetupRationale],
) -> list[str]:
    """校验一条 Setup 推荐的诚实性，返回违规清单（空 = 通过）。

    规则（任一违反即列入清单）：
      1. 每个非 None 参数必须有 rationale 覆盖（field==字段名 或 "all"）；
      2. 覆盖到实际改动的 rationale 必须有 ≥1 条 evidence，且 evidence.tool 在
         VALID_EVIDENCE_TOOLS 内；
      3. rationale 覆盖的字段在 params 里为 None → 告警（理由无对应改动）。
    """
    non_none_fields = set(params.model_dump(exclude_none=True))
    violations: list[str] = []

    # 规则 1：每个非 None 参数都要有 rationale 覆盖。
    for field in non_none_fields:
        if not any(r.field == field or r.field == "all" for r in rationale):
            violations.append(
                f"参数 {field!r} 有值但无对应 rationale（缺 field=={field!r} 或 'all'）"
            )

    # 规则 2 & 3：逐条 rationale 检查证据与对应性。
    for r in rationale:
        if r.field != "all" and r.field not in non_none_fields:
            # 规则 3：理由覆盖的字段没有实际改动。
            violations.append(
                f"rationale field={r.field!r} 无对应参数改动（params 中为 None 或未提供）"
            )
            continue
        # 规则 2：覆盖到实际改动的 rationale 必须有证据。
        if not r.evidence:
            violations.append(f"rationale field={r.field!r} 缺少 evidence")
            continue
        for ev in r.evidence:
            if ev.tool not in VALID_EVIDENCE_TOOLS:
                violations.append(
                    f"rationale field={r.field!r} 的 evidence.tool={ev.tool!r} 不在允许列表"
                )

    return violations
