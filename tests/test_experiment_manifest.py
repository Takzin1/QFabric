"""Preregistered offline experiments: review gate, structured results, exact replay."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from qfabric.orchestration import (
    ANALYSES,
    MANIFEST_REVIEW_VERSION,
    RESULT_VERSION,
    make_manifest_review,
    parse_manifest,
    replay_experiment,
    run_experiment,
)

FIXTURES = Path(__file__).parent / "fixtures"
SPEC = (FIXTURES / "decoder_benchmark.synthetic.json").read_bytes()
MANIFEST = (FIXTURES / "experiment_manifest.synthetic.json").read_bytes()
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "quantum_dataset_baseline.py"
_CLI_SPEC = importlib.util.spec_from_file_location("dataset_cli_for_experiments", SCRIPT)
assert _CLI_SPEC and _CLI_SPEC.loader
cli = importlib.util.module_from_spec(_CLI_SPEC)
_CLI_SPEC.loader.exec_module(cli)


def _manifest(**changes) -> bytes:
    doc = json.loads(MANIFEST)
    for path, value in changes.items():
        target = doc
        *parents, leaf = path.split("__")
        for part in parents:
            target = target[int(part) if part.isdigit() else part]
        target[leaf] = value
    return json.dumps(doc).encode()


def _approve(manifest: bytes) -> bytes:
    review = make_manifest_review(manifest, reviewer_label="test reviewer", decision="approve")
    return json.dumps(review).encode()


def test_fixture_manifest_pins_the_fixture_spec_bytes() -> None:
    manifest = parse_manifest(MANIFEST)
    assert manifest["inputs"][0]["sha256"] == hashlib.sha256(SPEC).hexdigest()
    assert manifest["requestedAction"] == "offline_analysis_only"


def test_completed_run_evaluates_the_preregistered_endpoint() -> None:
    result = run_experiment(MANIFEST, {"spec": SPEC})
    assert result["schemaVersion"] == RESULT_VERSION and result["status"] == "completed"
    assert result["endpoint"] == {
        "metric": "oracleAgreementFraction", "subject": "majority_vote", "minimum": 1.0,
        "observed": 1.0, "status": "met", "preregistered": True,
    }
    assert result["failure"] is None
    assert result["analysisReport"]["specSha256"] == result["inputs"][0]["sha256"]
    for flag in ("automaticExecution", "hardwareDispatchAllowed", "physicalMeasurement"):
        assert result[flag] is False
    assert result["humanReviewed"] is False and result["reviewSha256"] is None


def test_falsified_hypothesis_is_reported_as_not_met_not_hidden() -> None:
    manifest = _manifest(endpoint__subject="negative_control_prefix")
    result = run_experiment(manifest, {"spec": SPEC})
    assert result["status"] == "completed"
    assert result["endpoint"]["status"] == "not_met" and result["endpoint"]["observed"] < 0.7


def test_model_originated_manifest_cannot_run_without_bound_human_approval() -> None:
    manifest = _manifest(source__origin="unverified_model")
    with pytest.raises(ValueError, match="requires an approving human review"):
        run_experiment(manifest, {"spec": SPEC})
    rejection = json.dumps(
        make_manifest_review(manifest, reviewer_label="r", decision="reject")
    ).encode()
    with pytest.raises(ValueError, match="not an approval of exactly this manifest"):
        run_experiment(manifest, {"spec": SPEC}, review_raw=rejection)
    # An approval of a different manifest (even by one byte) is not transferable.
    with pytest.raises(ValueError, match="not an approval of exactly this manifest"):
        run_experiment(manifest, {"spec": SPEC}, review_raw=_approve(MANIFEST))
    result = run_experiment(manifest, {"spec": SPEC}, review_raw=_approve(manifest))
    assert result["humanReviewed"] is True and result["status"] == "completed"
    assert result["declaredOrigin"]["origin"] == "unverified_model"


@pytest.mark.parametrize("field, value", [
    ("reviewerAuthenticated", True), ("hardwareDispatchAllowed", True),
    ("automaticExecution", 0), ("status", "approved_for_hardware"), ("extra", "x"),
])
def test_tampered_review_records_are_refused(field, value) -> None:
    manifest = _manifest(source__origin="unverified_model")
    review = {**json.loads(_approve(manifest)), field: value}
    with pytest.raises(ValueError, match="not an approval"):
        run_experiment(manifest, {"spec": SPEC}, review_raw=json.dumps(review).encode())


def test_review_is_self_attested_and_never_releases_hardware() -> None:
    review = make_manifest_review(MANIFEST, reviewer_label=" A. Reviewer ", decision="approve")
    assert review["schemaVersion"] == MANIFEST_REVIEW_VERSION
    assert review["status"] == "approved_for_offline_analysis"
    assert review["reviewerAuthenticated"] is False
    assert review["hardwareDispatchAllowed"] is False and review["automaticExecution"] is False
    assert review["manifestSha256"] == hashlib.sha256(MANIFEST).hexdigest()
    for label, decision in (("", "approve"), ("r", "execute"), ("r" * 121, "approve")):
        with pytest.raises(ValueError):
            make_manifest_review(MANIFEST, reviewer_label=label, decision=decision)


def test_wrong_input_bytes_become_a_structured_reproducible_failure() -> None:
    altered = SPEC.replace(b"20261116", b"20261117")
    result = run_experiment(MANIFEST, {"spec": altered})
    assert result["status"] == "failed" and result["analysisReport"] is None
    assert result["failure"] == {
        "stage": "input_verification",
        "error": "input 'spec' differs from its preregistered SHA-256",
    }
    assert result["endpoint"]["status"] == "not_evaluated"
    assert result["endpoint"]["observed"] is None
    assert result == run_experiment(MANIFEST, {"spec": altered})
    for inputs in ({}, {"spec": SPEC, "extra": b"{}"}, {"other": SPEC}):
        assert run_experiment(MANIFEST, inputs)["failure"]["stage"] == "input_verification"


def test_analysis_stage_failures_are_reported_with_their_stage() -> None:
    measured = SPEC.replace(b'"synthetic_fixture"', b'"measured_syndromes"')
    manifest = _manifest(inputs__0__sha256=hashlib.sha256(measured).hexdigest())
    result = run_experiment(manifest, {"spec": measured})
    assert result["failure"]["stage"] == "analysis"
    assert "no authenticated syndrome-level measurement source" in result["failure"]["error"]
    # A manifest may not relabel a synthetic analysis as measured evidence.
    relabelled = _manifest(inputs__0__provenance="measured")
    failure = run_experiment(relabelled, {"spec": SPEC})["failure"]
    assert failure["stage"] == "analysis" and "provenance differs" in failure["error"]
    unknown = run_experiment(_manifest(endpoint__subject="no_such_decoder"), {"spec": SPEC})
    assert unknown["failure"]["stage"] == "analysis"


def test_replay_reproduces_the_result_exactly_and_detects_any_edit() -> None:
    stored = run_experiment(MANIFEST, {"spec": SPEC})
    raw = json.dumps(stored, indent=2).encode()
    verdict = replay_experiment(MANIFEST, {"spec": SPEC}, raw)
    assert verdict["identical"] is True
    assert verdict["storedDigest"] == verdict["recomputedDigest"] == stored["resultDigest"]
    for edited in (
        {**stored, "endpoint": {**stored["endpoint"], "observed": 0.99}},
        {**stored, "physicalMeasurement": True},
        {**stored, "hardwareDispatchAllowed": 0},
        {**stored, "status": "completed", "note": "validated on hardware"},
    ):
        verdict = replay_experiment(MANIFEST, {"spec": SPEC}, json.dumps(edited).encode())
        assert verdict["identical"] is False


@pytest.mark.parametrize("changes", [
    {"schemaVersion": "qfabric-experiment-manifest/2"},
    {"kind": "hardware_run"},
    {"requestedAction": "execute_on_qick"},
    {"requestedAction": "acquire"},
    {"analysis": "os.system"},
    {"analysis": ["decoder_benchmark"]},
    {"source__origin": "verified_model"},
    {"inputs": []},
    {"inputs__0__role": "dataset"},
    {"inputs__0__sha256": "A" * 64},
    {"inputs__0__provenance": "validated"},
    {"endpoint__metric": "quantumAdvantage"},
    {"endpoint__minimum": 1.5},
    {"endpoint__minimum": True},
    {"endpoint__minimum": float("nan")},
    {"hypothesis": ""},
    {"hypothesis": "x" * 601},
    {"experimentId": 7},
])
def test_untrusted_manifest_fails_closed(changes) -> None:
    with pytest.raises((ValueError, TypeError)):
        parse_manifest(_manifest(**changes))


def test_manifest_reader_refuses_unknown_fields_duplicates_and_oversize() -> None:
    with pytest.raises(ValueError, match="versioned contract"):
        parse_manifest(_manifest(hardwareTarget="qick-board-1"))
    doubled = MANIFEST.replace(
        b'"requestedAction": "offline_analysis_only"',
        b'"requestedAction": "execute", "requestedAction": "offline_analysis_only"',
    )
    assert doubled != MANIFEST
    with pytest.raises(ValueError, match="duplicate JSON key"):
        parse_manifest(doubled)
    with pytest.raises(ValueError, match="maximum size"):
        parse_manifest(MANIFEST + b" " * 17_000)


def test_analysis_allowlist_contains_no_hardware_path() -> None:
    assert set(ANALYSES) == {"decoder_benchmark"}
    source = (Path(__file__).resolve().parents[1] / "src/qfabric/orchestration.py").read_text()
    for forbidden in ("import qick", "from qick", "acquire(", "subprocess", "urllib", "socket"):
        assert forbidden not in source


def test_cli_review_run_replay_cycle_and_exit_codes(tmp_path, capsys) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_bytes(_manifest(source__origin="unverified_model"))
    spec = str(FIXTURES / "decoder_benchmark.synthetic.json")
    review, result = tmp_path / "review.json", tmp_path / "result.json"
    run = ["experiment-run", str(manifest), "--spec", spec, "--output", str(result)]
    assert cli.main(run) == 1 and not result.exists()  # no review: refused, nothing written
    assert cli.main([
        "experiment-review", str(manifest), "--reviewer-label", "ci", "--decision", "approve",
        "--output", str(review),
    ]) == 0
    assert cli.main([*run, "--review", str(review)]) == 0
    assert cli.main([*run, "--review", str(review)]) == 1  # evidence is never overwritten
    replay = ["experiment-replay", str(manifest), str(result), "--spec", spec,
              "--review", str(review)]
    assert cli.main(replay) == 0
    stored = json.loads(result.read_text())
    stored["endpoint"]["observed"] = 0.5
    result.write_text(json.dumps(stored))
    assert cli.main(replay) == 3
    capsys.readouterr()
    assert cli.main(["decoder-benchmark", spec]) == 0
    assert json.loads(capsys.readouterr().out)["dataProvenance"] == "synthetic"
    assert cli.main(["decoder-runtime", spec]) == 0
    assert json.loads(capsys.readouterr().out)["comparableToHardwareDecoderLatency"] is False


def test_cli_endpoint_not_met_exits_two(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_bytes(_manifest(endpoint__subject="negative_control_prefix"))
    spec = str(FIXTURES / "decoder_benchmark.synthetic.json")
    assert cli.main(["experiment-run", str(manifest), "--spec", spec]) == 2
