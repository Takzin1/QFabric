"""Offline reproducibility tests: source-byte substitution must fail closed."""

import copy
import importlib
import json
import sys
from pathlib import Path

import pytest

# scripts/ is deliberately an un-packaged CLI directory in this repository.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
crystaltwin_bridge = importlib.import_module("crystaltwin_bridge")
research_bundle = importlib.import_module("research_bundle")

SNAPSHOT_FILE = Path(__file__).parent / "fixtures" / "crystaltwin_snapshot.synthetic.json"


def _pair() -> tuple[bytes, bytes]:
    raw = SNAPSHOT_FILE.read_bytes()
    report = crystaltwin_bridge.make_report(raw, shots=256, backend="cpu")
    return raw, json.dumps(report, allow_nan=False).encode("utf-8")


def _encoded(value: dict) -> bytes:
    return json.dumps(value, allow_nan=False).encode("utf-8")


def test_exact_pair_creates_and_verifies_deterministic_manifest() -> None:
    snapshot, report = _pair()
    bundle = research_bundle.build_bundle(snapshot, report)
    assert bundle["kind"] == "synthetic_offline_interoperability"
    assert bundle["physicalMeasurement"] is False
    assert bundle["hardwareExecuted"] is False
    assert bundle["scientificReplication"] is False
    assert bundle["integrityChecks"]["exactSourceBytes"] is True
    assert bundle["environment"] == {"analyticsBackend": "cpu", "shots": 256}
    assert research_bundle.build_bundle(snapshot, report) == bundle
    assert research_bundle.verify_bundle(snapshot, report, _encoded(bundle)) == bundle


def test_swapped_snapshot_and_tampered_report_are_rejected() -> None:
    snapshot, report = _pair()
    bundle = _encoded(research_bundle.build_bundle(snapshot, report))
    with pytest.raises(ValueError, match="SHA-256"):
        research_bundle.verify_bundle(snapshot + b" ", report, bundle)
    parsed = json.loads(report)
    parsed["qfabric"]["hardwareExecuted"] = True
    with pytest.raises(ValueError, match="hardware"):
        research_bundle.build_bundle(snapshot, _encoded(parsed))


@pytest.mark.parametrize("field,value", [
    ("physicalMeasurement", True),
    ("hardwareExecuted", True),
    ("scientificReplication", True),
    ("primaryResult", "quantum_advantage_confirmed"),
])
def test_manifest_claim_mutation_is_rejected(field: str, value: object) -> None:
    snapshot, report = _pair()
    altered = copy.deepcopy(research_bundle.build_bundle(snapshot, report))
    altered[field] = value
    with pytest.raises(ValueError, match="manifest differs"):
        research_bundle.verify_bundle(snapshot, report, _encoded(altered))


def test_duplicate_json_keys_and_oversized_manifest_are_rejected() -> None:
    snapshot, report = _pair()
    with pytest.raises(ValueError, match="duplicate JSON key"):
        research_bundle.verify_bundle(snapshot, report, b'{"schemaVersion":"x","schemaVersion":"y"}')
    with pytest.raises(ValueError, match="16 KiB"):
        research_bundle.verify_bundle(snapshot, report, b" " * (research_bundle.MAX_MANIFEST_BYTES + 1))


def test_offline_cli_round_trip(tmp_path: Path) -> None:
    snapshot, report = _pair()
    s, r, m = (tmp_path / name for name in ("s.json", "r.json", "m.json"))
    s.write_bytes(snapshot)
    r.write_bytes(report)
    assert research_bundle.main([str(s), str(r), str(m)]) == 0
    assert research_bundle.main([str(s), str(r), str(m), "--verify"]) == 0
    with pytest.raises(FileExistsError):
        research_bundle.main([str(s), str(r), str(m)])
