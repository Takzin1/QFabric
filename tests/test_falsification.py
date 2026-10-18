"""Evidence separation, false-claim detection and synthetic decision tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from qfabric.falsification import (
    RESULT_SCHEMA,
    evaluate_synthetic_falsification,
    validate_baseline_sources,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (ROOT / "data/independent_baseline_sources.json").read_bytes()
COUNTS = (ROOT / "tests/fixtures/falsification.synthetic.json").read_bytes()
SPEC = importlib.util.spec_from_file_location(
    "qfabric_falsification_cli", ROOT / "scripts/quantum_dataset_baseline.py"
)
assert SPEC and SPEC.loader
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


def _raw(x: object) -> bytes:
    return json.dumps(x, ensure_ascii=False, allow_nan=True).encode()


def test_source_catalog_has_paper_and_data_links_but_zero_verification() -> None:
    sources = validate_baseline_sources(SOURCES)["sources"]
    assert len(sources) == 4
    assert {s["evaluationAxis"] for s in sources} == {
        "mirror_rb_crosstalk", "mid_circuit_measurement_spectator",
        "gate_set_tomography_validation", "quantum_volume_external_validity",
    }
    assert all(s["localSha256"] is None for s in sources)
    assert all(s["downloadStatus"] == "not_downloaded" for s in sources)
    assert all(s["licenseVerified"] is False for s in sources)
    assert all(s["measurementsVerified"] is False for s in sources)
    assert all(s["reproduced"] is False for s in sources)
    assert sources[2]["format"] == "pcl"
    assert sources[2]["dataOrigin"] == "simulation_claim"


def test_synthetic_falsification_yields_three_different_decisions() -> None:
    report = evaluate_synthetic_falsification(COUNTS, sources_raw=SOURCES)
    assert report["schemaVersion"] == RESULT_SCHEMA
    decisions = [profile["primaryVerdict"] for profile in report["profiles"]]
    assert decisions == [
        "consistent_with_improvement",
        "falsifies_minimum_improvement",
        "inconclusive",
    ]
    assert report["measurementVerified"] is False
    assert report["hardwareExecuted"] is False
    assert report["scientificReplication"] is False
    for item in report["profiles"]:
        assert item["conservativeDifferenceLower"] <= item["estimatedImprovement"]
        assert item["estimatedImprovement"] <= item["conservativeDifferenceUpper"]
        assert item["measurementVerified"] is False


def test_higher_is_better_configurable_direction_changes_result() -> None:
    fixture = json.loads(COUNTS)
    fixture["profiles"] = [fixture["profiles"][0]]
    fixture["profiles"][0]["direction"] = "higher_is_better"
    report = evaluate_synthetic_falsification(_raw(fixture), sources_raw=SOURCES)
    assert report["profiles"][0]["primaryVerdict"] == "falsifies_minimum_improvement"


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("confidenceLevel", True),
        ("confidenceLevel", 1.0),
        ("confidenceLevel", 0.5),
        ("confidenceLevel", float("nan")),
        ("minimumImprovement", -0.1),
        ("minimumImprovement", float("inf")),
        ("minimumImprovement", 10**400),
        ("minimumShotsPerArm", 0),
        ("minimumShotsPerArm", True),
        ("minimumShotsPerArm", 1_000_001),
        ("samplingAssumption", "paired_clustered"),
        ("noiseModel", "measured"),
        ("analysisPlan", "post_hoc_optimization"),
        ("metric", "quantum_volume"),
        ("sourceBaselineId", "ALT-999"),
        ("direction", "ambiguous"),
        ("sensitivityThresholds", [0.04]),
        ("sensitivityThresholds", [0.02, 0.02]),
    ],
)
def test_invalid_or_correlated_profile_never_produces_verdict(
    field: str, replacement: object
) -> None:
    fixture = json.loads(COUNTS)
    fixture["profiles"][0][field] = replacement
    with pytest.raises((ValueError, TypeError)):
        evaluate_synthetic_falsification(_raw(fixture), sources_raw=SOURCES)


@pytest.mark.parametrize("arm", ["control", "candidate"])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("shots", 0), ("shots", True), ("shots", 10**400),
        ("events", -1), ("events", True), ("events", 10**400),
    ],
)
def test_invalid_binomial_counts_refused(arm: str, field: str, value: object) -> None:
    fixture = json.loads(COUNTS)
    fixture["profiles"][0][arm][field] = value
    with pytest.raises((ValueError, TypeError)):
        evaluate_synthetic_falsification(_raw(fixture), sources_raw=SOURCES)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("datasetUrl", "https://evil.example/mirror"),
        ("filename", "../supplement.zip"),
        ("publishedMd5", "0" * 32),
        ("licenseVerified", True),
        ("measurementsVerified", True),
        ("reproduced", True),
        ("localSha256", "0" * 64),
        ("downloadStatus", "downloaded"),
        ("dataOrigin", "measured_claim"),
    ],
)
def test_sources_never_silently_promote_evidence(field: str, value: object) -> None:
    obj = json.loads(SOURCES)
    obj["sources"][0][field] = value
    with pytest.raises((ValueError, TypeError)):
        validate_baseline_sources(_raw(obj))


@pytest.mark.parametrize(
    "data",
    [
        b'{"x":NaN}',
        b'{"schemaVersion":"x","schemaVersion":"x"}',
        b'{"x":1e309}',
        b" " * (64 * 1024 + 1),
    ],
)
def test_malformed_synthetic_input_refused(data: bytes) -> None:
    with pytest.raises((ValueError, TypeError)):
        evaluate_synthetic_falsification(data, sources_raw=SOURCES)


def test_fixture_rejects_real_data_claims_and_duplicate_profiles() -> None:
    obj = json.loads(COUNTS)
    obj["kind"] = "experimental_measurements"
    with pytest.raises(ValueError):
        evaluate_synthetic_falsification(_raw(obj), sources_raw=SOURCES)
    obj = json.loads(COUNTS)
    obj["profiles"][1]["id"] = obj["profiles"][0]["id"]
    with pytest.raises(ValueError, match="unique"):
        evaluate_synthetic_falsification(_raw(obj), sources_raw=SOURCES)


def test_cli_validates_and_runs_synthetic_only(tmp_path: Path, capsys) -> None:
    sources = ROOT / "data/independent_baseline_sources.json"
    fixture = ROOT / "tests/fixtures/falsification.synthetic.json"
    assert cli.main(["validate-alternative-sources", str(sources)]) == 0
    assert json.loads(capsys.readouterr().out)["filesDownloaded"] == 0
    out = tmp_path / "report.json"
    assert cli.main([
        "synthetic-falsification", str(fixture), "--sources", str(sources),
        "--output", str(out),
    ]) == 0
    report = json.loads(out.read_text())
    assert report["measurementVerified"] is False
    assert len(report["profiles"]) == 3
    assert cli.main([
        "synthetic-falsification", str(fixture), "--sources", str(sources),
        "--output", str(out),
    ]) == 1
