"""L4 确定性计算 —— A-B 实验评估（PHASE 8）。

把一次 Setup 实验（BASELINE vs TEST）的两组完赛圈，经 `analysis.compare` 归约成
delta 指标，并按确定性规则推导 `ValidationStatus`。

状态推导（全确定性，无模型；阈值可配置）：
  - 两侧均无有效圈 → INCONCLUSIVE
  - 任一侧有效圈 < min_samples → PARTIALLY_VALIDATED（有数据但样本不足）
  - 否则按最快圈差值 best_delta（负 = test 更快）：
      best_delta ≤ -min_delta_s → VALIDATED（test 明显更快）
      best_delta ≥ +min_delta_s → NOT_VALIDATED（test 明显更慢）
      |best_delta| < min_delta_s → INCONCLUSIVE（噪声内，无法判定）

诚实性：结果只说明「圈速更快/更慢」，不归因（天气/油量/胎况等混杂因素见
`Experiment.test_conditions`，未做因果推断）。
"""

from __future__ import annotations

from analysis.compare import compare_laps
from store.schemas import Confidence, Experiment, LapRecord, ValidationStatus


def evaluate_experiment(
    experiment: Experiment,
    baseline_laps: list[LapRecord],
    test_laps: list[LapRecord],
    *,
    min_samples: int = 3,
    min_delta_s: float = 0.05,
) -> Experiment:
    """运行一次实验：填 `delta_metrics` + 推导 `status`，返回新 Experiment（不改入参）。

    参数：
      experiment：待评估的实验（exp_id/hypothesis/setup 版本/条件已填）。
      baseline_laps / test_laps：两侧的完赛圈（LapRecord，L4 已换算）。
      min_samples：判定「样本足够」的最小有效圈数。
      min_delta_s：判定「有明显差异」的最快圈差值阈值（秒）。
    """
    result = compare_laps(baseline_laps, test_laps)

    if result.baseline_n == 0 and result.test_n == 0:
        status = ValidationStatus.INCONCLUSIVE
    elif result.baseline_n < min_samples or result.test_n < min_samples:
        status = ValidationStatus.PARTIALLY_VALIDATED
    elif result.best_delta is None:
        status = ValidationStatus.INCONCLUSIVE
    elif result.best_delta <= -min_delta_s:
        status = ValidationStatus.VALIDATED
    elif result.best_delta >= min_delta_s:
        status = ValidationStatus.NOT_VALIDATED
    else:
        status = ValidationStatus.INCONCLUSIVE

    # 置信度随判定强度走：两侧样本足够且有明确方向 → HIGH；样本不足 → MEDIUM；无法判定 → LOW。
    if status in (ValidationStatus.VALIDATED, ValidationStatus.NOT_VALIDATED):
        confidence = Confidence.HIGH
    elif status is ValidationStatus.PARTIALLY_VALIDATED:
        confidence = Confidence.MEDIUM
    else:
        confidence = Confidence.LOW

    return experiment.model_copy(
        update={
            "status": status,
            "confidence": confidence,
            "delta_metrics": result.as_dict(),
        }
    )
