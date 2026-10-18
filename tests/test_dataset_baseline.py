"""Regression tests for source-only registry and binomial synthetic baseline."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from qfabric.dataset_baseline import (
    BASELINE_VERSION,
    CATALOG_VERSION,
    compute_synthetic_count_baseline,
    validate_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = (ROOT / "data/quantum_dataset_candidates.json").read_bytes()
COUNTS = (ROOT / "tests/fixtures/quantum_counts.synthetic.json").read_bytes()
SPEC = importlib.util.spec_from_file_location(
    "quantum_dataset_baseline_script", ROOT / "scripts/quantum_dataset_baseline.py"
)
assert SPEC and SPEC.loader
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


def _encoded(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def test_metadata_catalog_records_remain_unverified() -> None:
    catalog = validate_catalog(CATALOG)
    assert catalog["schemaVersion"] == CATALOG_VERSION
    assert len(catalog["datasets"]) >= 10
    assert {item["priority"] for item in catalog["datasets"]} >= {"P0", "P1"}
    assert all(item["rawSha256"] is None for item in catalog["datasets"])
    assert all(item["licenseIdentifier"] is None for item in catalog["datasets"])
    assert all(item["ingestStatus"] == "not_downloaded" for item in catalog["datasets"])
    assert len({item["datasetId"] for item in catalog["datasets"]}) == len(catalog["datasets"])


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("rawSha256", "a" * 64),
        ("licenseStatus", "verified"),
        ("licenseIdentifier", "CC-BY-4.0"),
        ("unitStatus", "verified"),
        ("ingestStatus", "accepted"),
        ("recordUrl", "http://zenodo.org/records/8363718"),
        ("recordUrl", "https://evil.example/records/8363718"),
        ("recordUrl", "https://zenodo.org/records/999"),
        ("filename", "../escape.csv"),
        ("filename", "/tmp/test.csv"),
        ("filename", "C:\\\\escape.csv"),
        ("filename", ".."),
        ("datasetDoi", "10.5281/zenodo.999"),
        ("publishedMd5", "definitely-not-a-digest"),
        ("provenance", "scientifically_verified"),
        ("priority", "P-1"),
        ("paperDoi", "not-a-doi"),
    ],
)
def test_candidate_cannot_promote_unverified_source(key, value) -> None:
    doc = json.loads(CATALOG)
    doc["datasets"][0][key] = value
    with pytest.raises((ValueError, TypeError)):
        validate_catalog(_encoded(doc))


def test_rejects_duplicate_dataset_id_and_extra_fields() -> None:
    doc = json.loads(CATALOG)
    doc["datasets"][1]["datasetId"] = doc["datasets"][0]["datasetId"]
    with pytest.raises(ValueError, match="unique"):
        validate_catalog(_encoded(doc))
    doc = json.loads(CATALOG)
    doc["datasets"][0]["hardwareExecuted"] = True
    with pytest.raises(ValueError, match="fields"):
        validate_catalog(_encoded(doc))


def test_catalog_json_must_be_unambiguous_and_bounded() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        validate_catalog(b'{"schemaVersion":1,"schemaVersion":2}')
    with pytest.raises(ValueError):
        validate_catalog(b'{"status":NaN}')
    with pytest.raises(ValueError):
        validate_catalog(b"[" * 10_000)
    with pytest.raises(ValueError, match="byte length"):
        validate_catalog(b"x" * (128 * 1024 + 1))


def test_synthetic_count_baseline_known_reference_values() -> None:
    report = compute_synthetic_count_baseline(COUNTS)
    assert report["schemaVersion"] == BASELINE_VERSION
    assert report["kind"] == "synthetic_binomial_reference"
    assert report["hardwareExecuted"] is False
    assert report["measurementVerified"] is False
    import hashlib
    assert report["inputSha256"] == hashlib.sha256(COUNTS).hexdigest()
    low, high = report["results"]
    assert low["errorRate"] == 0.05
    assert low["wilson95Lower"] == pytest.approx(0.02154367915436796)
    assert low["wilson95Upper"] == pytest.approx(0.11175046923191913)
    assert high["errorRate"] == 0.15
    assert high["wilson95Lower"] == pytest.approx(0.10713593562241995)
    assert high["wilson95Upper"] == pytest.approx(0.20605579284166659)


@pytest.mark.parametrize(
    ("shots", "errors"),
    [(0, 0), (False, 0), (100, True), (100, -1), (100, 101),
     (10.0, 2), (100, float("nan")), (100, float("inf"))],
)
def test_invalid_count_values_rejected(shots, errors) -> None:
    doc = json.loads(COUNTS)
    doc["groups"][0].update(shots=shots, errors=errors)
    with pytest.raises(ValueError):
        compute_synthetic_count_baseline(_encoded(doc))


def test_rejects_false_measured_label_and_unsupported_fields() -> None:
    doc = json.loads(COUNTS)
    doc["kind"] = "measured"
    with pytest.raises(ValueError, match="synthetic"):
        compute_synthetic_count_baseline(_encoded(doc))
    doc = json.loads(COUNTS)
    doc["groups"][0]["qickAcquire"] = True
    with pytest.raises(ValueError, match="fields"):
        compute_synthetic_count_baseline(_encoded(doc))


def test_rejects_duplicate_group_names_and_duplicate_json_keys() -> None:
    doc = json.loads(COUNTS)
    doc["groups"][1]["name"] = doc["groups"][0]["name"]
    with pytest.raises(ValueError, match="duplicate"):
        compute_synthetic_count_baseline(_encoded(doc))
    with pytest.raises(ValueError, match="duplicate JSON"):
        compute_synthetic_count_baseline(b'{"kind":"synthetic_fixture","kind":"synthetic_fixture"}')


@pytest.mark.parametrize("errors", [0, 1])
def test_wilson_edge_cases_are_bounded(errors) -> None:
    doc = json.loads(COUNTS)
    doc["groups"] = [{"name": "extreme", "shots": 1, "errors": errors}]
    result = compute_synthetic_count_baseline(_encoded(doc))["results"][0]
    assert 0 <= result["wilson95Lower"] <= result["errorRate"]
    assert result["errorRate"] <= result["wilson95Upper"] <= 1


def test_cli_catalog_and_synthetic_baseline(tmp_path) -> None:
    assert cli.main(["validate-catalog", str(ROOT / "data/quantum_dataset_candidates.json")]) == 0
    target = tmp_path / "synthetic-report.json"
    assert cli.main([
        "synthetic-baseline", str(ROOT / "tests/fixtures/quantum_counts.synthetic.json"),
        "--output", str(target)
    ]) == 0
    report = json.loads(target.read_text())
    assert report["dataProvenance"] == "synthetic_fixture"
    assert report["measurementVerified"] is False
    assert len(report["results"]) == 2
