"""Unit tests：Setup 推荐（PHASE 12）—— 诚实性校验 + recommend_setup/list_recommendations。"""

import pytest

from analysis.recommend import validate_recommendation, weakest_confidence
from store.experiment_store import ExperimentStore
from store.schemas import Confidence, EvidenceRef, SetupParams, SetupRationale, SourceLevel
from tools import build_registry


def _evidence(tool="get_lap", level=SourceLevel.DERIVED, conf=Confidence.HIGH) -> EvidenceRef:
    return EvidenceRef(tool=tool, source_level=level, confidence=conf, summary="S2 慢 0.3s")


def _rationale(field="front_wing", change="+2", reason="S2 出弯抓地不足", evidence=None) -> SetupRationale:
    return SetupRationale(field=field, change=change, reason=reason, evidence=evidence or [])


# ---------------------------------------------------------------------------
# validate_recommendation 诚实性不变量
# ---------------------------------------------------------------------------

def test_no_rationale_for_set_param():
    params = SetupParams(front_wing=30)
    violations = validate_recommendation(params, [])
    assert violations
    assert any("front_wing" in v for v in violations)


def test_rationale_missing_evidence():
    params = SetupParams(front_wing=30)
    r = _rationale("front_wing", evidence=[])
    violations = validate_recommendation(params, [r])
    assert any("缺少 evidence" in v for v in violations)


def test_invalid_evidence_tool():
    params = SetupParams(front_wing=30)
    r = _rationale("front_wing", evidence=[_evidence(tool="save_setup")])
    violations = validate_recommendation(params, [r])
    assert any("不在允许列表" in v for v in violations)


def test_rationale_for_none_field_warns():
    params = SetupParams(front_wing=30)
    r = _rationale("rear_wing", evidence=[_evidence()])
    violations = validate_recommendation(params, [r])
    assert any("无对应参数改动" in v for v in violations)


def test_valid_passes():
    params = SetupParams(front_wing=30)
    r = _rationale("front_wing", evidence=[_evidence()])
    assert validate_recommendation(params, [r]) == []


def test_all_rationale_covers_all_params():
    params = SetupParams(front_wing=30, rear_wing=25)
    r = _rationale("all", change="整体提高下压力", evidence=[_evidence()])
    assert validate_recommendation(params, [r]) == []


def test_weakest_confidence():
    assert weakest_confidence([Confidence.HIGH, Confidence.LOW]) is Confidence.LOW
    assert weakest_confidence([Confidence.HIGH, Confidence.MEDIUM]) is Confidence.MEDIUM
    assert weakest_confidence([Confidence.HIGH, Confidence.HIGH]) is Confidence.HIGH
    assert weakest_confidence([]) is Confidence.LOW


# ---------------------------------------------------------------------------
# recommend_setup / list_recommendations Tool
# ---------------------------------------------------------------------------

def _payload():
    return dict(
        recommendation_id="rec1",
        track_id="shanghai",
        setup_version="v2",
        summary="提高前翼下压力以改善 S2 出弯",
        params={"front_wing": 32},
        rationale=[
            {
                "field": "front_wing",
                "change": "+2",
                "reason": "S2 出弯抓地不足",
                "evidence": [
                    {
                        "tool": "get_sector",
                        "source_level": "DERIVED",
                        "confidence": "MEDIUM",
                        "summary": "S2 exit_speed 92km/h，慢基准 0.3s",
                    }
                ],
            }
        ],
    )


def test_recommend_setup_persists_and_lists(tmp_path):
    store = ExperimentStore(tmp_path / "t.sqlite3")
    registry = build_registry(store)
    result = registry.call("recommend_setup", **_payload())
    listed = registry.call("list_recommendations")
    filtered = registry.call("list_recommendations", status="PREDICTED")
    store.close()

    assert result.source_level is SourceLevel.HYPOTHESIS
    assert result.confidence is Confidence.MEDIUM  # weakest-link = 最弱证据
    assert result.data["status"] == "PREDICTED"
    assert result.data["params"]["front_wing"] == 32

    assert len(listed.data) == 1
    assert listed.data[0]["recommendation_id"] == "rec1"
    assert listed.data[0]["source_level"] == "HYPOTHESIS"
    assert len(filtered.data) == 1


def test_recommend_setup_rejects_number_without_evidence(tmp_path):
    store = ExperimentStore(tmp_path / "t.sqlite3")
    registry = build_registry(store)
    payload = _payload()
    payload["rationale"] = []  # front_wing=32 无 rationale → 无据给数字
    result = registry.call("recommend_setup", **payload)
    listed = registry.call("list_recommendations")
    store.close()

    assert result.data is None
    assert result.notes
    assert listed.data == []  # 未落库


def test_recommend_setup_rejects_invalid_evidence_tool(tmp_path):
    store = ExperimentStore(tmp_path / "t.sqlite3")
    registry = build_registry(store)
    payload = _payload()
    payload["rationale"][0]["evidence"][0]["tool"] = "save_setup"  # 写 Tool 不可作证据
    result = registry.call("recommend_setup", **payload)
    store.close()

    assert result.data is None
    assert any("不在允许列表" in n for n in result.notes)
