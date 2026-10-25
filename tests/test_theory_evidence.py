"""Evidence metadata checks; this test never executes an experiment or fetches papers."""
import json
from pathlib import Path

import pytest

from qfabric.theory_evidence import load_registry, validate_registry

REGISTRY = Path(__file__).resolve().parents[1] / "data" / "quantum_theory_evidence_v1.json"
RAW = REGISTRY.read_bytes()


def _with_change(index: int, key: str, value):
    doc = json.loads(RAW)
    doc["entries"][index][key] = value
    return json.dumps(doc, ensure_ascii=False).encode()


def test_curated_papers_are_unique_and_have_primary_dois():
    registry = load_registry(REGISTRY)
    assert registry["schemaVersion"] == "qfabric-quantum-theory-evidence/1"
    assert len(registry["entries"]) >= 10
    assert any(item["year"] == 2026 for item in registry["entries"])
    for item in registry["entries"]:
        assert item["primaryUrl"] == "https://doi.org/" + item["doi"]
        assert item["crystalTwinUse"] == "context_only_no_engine_calibration"
        assert item["reproductionStatus"] == "not_reproduced_in_either_repository"


def test_rejects_false_scientific_support_or_unauthenticated_citation():
    with pytest.raises(ValueError, match="unsupported scientific"):
        validate_registry(_with_change(0, "crystalTwinUse", "validated_kinetics"))
    with pytest.raises(ValueError, match="citation count"):
        doc = json.loads(RAW)
        doc["entries"][0]["citationSnapshot"]["count"] = True
        validate_registry(json.dumps(doc).encode())
    with pytest.raises(ValueError, match="DOI and original URL"):
        validate_registry(_with_change(0, "primaryUrl", "https://example.com/fake"))


def test_rejects_duplicate_reference_and_duplicate_json_members():
    doc = json.loads(RAW)
    doc["entries"].append(doc["entries"][0].copy())
    with pytest.raises(ValueError, match="duplicate paper"):
        validate_registry(json.dumps(doc).encode())
    with pytest.raises(ValueError, match="duplicate key"):
        validate_registry(b'{"schemaVersion": "x", "schemaVersion": "y"}')


def test_rejects_nan_unknown_keys_and_oversized_payloads():
    doc = json.loads(RAW)
    doc["entries"][0]["citationSnapshot"]["count"] = float("nan")
    with pytest.raises(ValueError, match="nonfinite"):
        validate_registry(json.dumps(doc).encode())
    doc = json.loads(RAW)
    doc["entries"][0]["hardwareExecuted"] = True
    with pytest.raises(ValueError, match="unexpected fields"):
        validate_registry(json.dumps(doc).encode())
    with pytest.raises(ValueError, match="bounded"):
        validate_registry(RAW * 20)
