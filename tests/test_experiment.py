"""Unit tests：L4 实验评估 + ExperimentStore 持久化（PHASE 8）。"""

import pytest

from analysis.experiment import evaluate_experiment
from store.experiment_store import ExperimentStore
from store.schemas import (
    Confidence,
    Experiment,
    LapRecord,
    SetupParams,
    SetupSnapshot,
    SourceLevel,
    ValidationStatus,
)


def _lap(lap_number, lap_time, valid=True) -> LapRecord:
    return LapRecord(
        source_level=SourceLevel.DERIVED,
        source="calc:lap_metrics",
        timestamp="2026-08-14T00:00:00+00:00",
        unit="s",
        confidence=Confidence.HIGH,
        lap_number=lap_number,
        session_uid=1,
        lap_time=lap_time,
        sector1=25.0,
        sector2=30.0,
        sector3=lap_time - 55.0,
        valid_flag=valid,
    )


def _experiment(**overrides) -> Experiment:
    d = dict(
        source_level=SourceLevel.DERIVED,
        source="calc:experiment",
        timestamp="2026-08-14T00:00:00+00:00",
        unit="s",
        confidence=Confidence.LOW,
        exp_id="exp1",
        hypothesis="test faster",
        setup_baseline_version="v1",
        setup_test_version="v2",
        status=ValidationStatus.PREDICTED,
        baseline_laps=[1, 2, 3],
        test_laps=[4, 5, 6],
    )
    d.update(overrides)
    return Experiment(**d)


def _three_laps(start, times):
    return [_lap(start + i, t) for i, t in enumerate(times)]


def test_validated_when_test_clearly_faster():
    baseline = _three_laps(1, [95.0, 96.0, 97.0])
    test = _three_laps(4, [94.0, 94.5, 95.0])
    result = evaluate_experiment(_experiment(), baseline, test)
    assert result.status is ValidationStatus.VALIDATED
    assert result.confidence is Confidence.HIGH
    assert result.delta_metrics["best_delta_s"] == pytest.approx(-1.0)


def test_not_validated_when_test_clearly_slower():
    baseline = _three_laps(1, [94.0, 94.5, 95.0])
    test = _three_laps(4, [95.0, 96.0, 97.0])
    result = evaluate_experiment(_experiment(), baseline, test)
    assert result.status is ValidationStatus.NOT_VALIDATED


def test_inconclusive_when_no_clear_delta():
    baseline = _three_laps(1, [95.0, 95.02, 95.03])
    test = _three_laps(4, [95.0, 95.01, 95.02])
    result = evaluate_experiment(_experiment(), baseline, test)
    assert result.status is ValidationStatus.INCONCLUSIVE
    assert result.confidence is Confidence.LOW


def test_partially_validated_when_samples_insufficient():
    baseline = [_lap(1, 95.0)]
    test = [_lap(4, 94.0)]
    result = evaluate_experiment(_experiment(), baseline, test)
    assert result.status is ValidationStatus.PARTIALLY_VALIDATED
    assert result.confidence is Confidence.MEDIUM


def test_inconclusive_when_no_valid_laps():
    result = evaluate_experiment(_experiment(), [], [])
    assert result.status is ValidationStatus.INCONCLUSIVE


def test_evaluate_does_not_mutate_input():
    experiment = _experiment()
    evaluate_experiment(experiment, _three_laps(1, [95.0, 96, 97]), _three_laps(4, [94.0, 94.5, 95]))
    assert experiment.status is ValidationStatus.PREDICTED
    assert experiment.delta_metrics == {}


# ---------------------------------------------------------------------------
# ExperimentStore 持久化
# ---------------------------------------------------------------------------

def test_setup_snapshot_roundtrip(tmp_path):
    store = ExperimentStore(tmp_path / "t.sqlite3")
    snapshot = SetupSnapshot(
        source_level=SourceLevel.GAME_DATA,
        source="game:car_setup",
        timestamp="2026-08-14T00:00:00+00:00",
        unit="setup",
        confidence=Confidence.HIGH,
        setup_version="v1",
        track_id="shanghai",
        name="baseline",
        params=SetupParams(front_wing=30, rear_wing=25, brake_bias=56.0),
    )
    store.save_setup(snapshot)
    loaded = store.get_setup("v1")
    store.close()

    assert loaded.setup_version == "v1"
    assert loaded.params.front_wing == 30
    assert loaded.params.brake_bias == pytest.approx(56.0)
    assert loaded.source_level is SourceLevel.GAME_DATA


def test_experiment_roundtrip(tmp_path):
    store = ExperimentStore(tmp_path / "t.sqlite3")
    experiment = _experiment(
        status=ValidationStatus.VALIDATED,
        delta_metrics={"best_delta_s": -1.0},
    )
    store.save_experiment(experiment)
    loaded = store.get_experiment("exp1")
    listed = store.list_experiments(status="VALIDATED")
    store.close()

    assert loaded.exp_id == "exp1"
    assert loaded.status is ValidationStatus.VALIDATED
    assert loaded.delta_metrics == {"best_delta_s": -1.0}
    assert len(listed) == 1
    assert listed[0].exp_id == "exp1"


def test_experiment_store_also_persists_raw(tmp_path):
    from ingest.receiver import TelemetryReceiver
    from mock.factory import build_session_datagram

    store = ExperimentStore(tmp_path / "t.sqlite3")
    receiver = TelemetryReceiver(port=12345)
    store.save(receiver._to_packet(build_session_datagram(weather=1), ("x", 1)))
    assert store.count() == 1
    store.close()
