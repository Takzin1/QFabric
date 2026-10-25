"""QFabric independently verifies evidence exported by CrystalPilot (TypeScript).

Fixtures were produced by CrystalTwinAI `scripts/export-evidence-fixtures.mts`
in OFFLINE fixture mode (no model call). They exercise cross-language
canonical JSON and re-run the real QFabric gate on TypeScript-produced bytes.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from qfabric.evidence import _js_number, canonical_json, canonical_sha256, verify_evidence

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]
NAMES = ["verified", "gate-rejected", "reviewer-rejected"]


def _raw(name: str) -> bytes:
    return (FIXTURES / f"crystalpilot_evidence.{name}.offline.json").read_bytes()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, "0"), (-0.0, "0"), (1.0, "1"), (80, "80"), (1.5, "1.5"), (-2.25, "-2.25"),
        (0.000123, "0.000123"), (1e-7, "1e-7"), (1.5e-7, "1.5e-7"), (123456.789, "123456.789"),
        (1e21, "1e+21"), (1.2e22, "1.2e+22"), (1e20, "100000000000000000000"),
        (5e-324, "5e-324"), (0.1 + 0.2, "0.30000000000000004"), (1 / 3, "0.3333333333333333"),
        (2.7079909909933875, "2.7079909909933875"), (0.000001, "0.000001"),
    ],
)
def test_ecmascript_number_formatting(value, expected) -> None:
    assert _js_number(value) == expected


def test_canonical_json_sorts_utf16_and_rejects_nonfinite() -> None:
    assert canonical_json({"b": 1, "a": [True, None, "é\n"]}) == '{"a":[true,null,"é\\n"],"b":1}'
    # U+FF61 sorts after U+1F600 in UTF-16 code units (surrogate 0xD83D < 0xFF61) — JCS order.
    assert canonical_json({"｡": 1, "\U0001f600": 2}) == '{"\U0001f600":2,"｡":1}'
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})


@pytest.mark.parametrize("name", NAMES)
def test_typescript_evidence_verifies_in_python(name) -> None:
    report = verify_evidence(_raw(name))
    assert report["overall"] == "PASS", report["checks"]
    assert report["integrity"] == "VERIFIED"
    ids = {c["id"]: c["status"] for c in report["checks"]}
    assert ids["snapshot_hash"] == "pass"
    assert ids["gate_recompute"] == "pass"
    if name == "verified":
        assert ids["review_recompute"] == "pass"
        assert ids["simulation_replay"] == "skip"


def test_canonical_digest_matches_typescript_digest() -> None:
    doc = json.loads(_raw("verified"))
    assert canonical_sha256(doc["body"]) == doc["integrity"]["bodySha256"]


def _tampered(mutate) -> dict:
    doc = json.loads(_raw("verified"))
    mutate(doc["body"]["run"])
    return verify_evidence(json.dumps(doc, ensure_ascii=False).encode())


def test_tampered_result_breaks_integrity() -> None:
    def edit(run):
        run["experiment"]["resultSummary"]["qualityScore"] = 99.9
    report = _tampered(edit)
    assert report["integrity"] == "MISMATCH"
    assert report["overall"] == "FAIL"


def test_tampered_snapshot_fails_hash_and_gate() -> None:
    def edit(run):
        run["snapshotText"] = run["snapshotText"].replace('"coolingRate": 1.8', '"coolingRate": 0.2')
    report = _tampered(edit)
    status = {c["id"]: c["status"] for c in report["checks"]}
    assert status["integrity"] == "fail"
    assert status["snapshot_hash"] == "fail"


def test_rehashed_forgery_still_fails_gate_recompute() -> None:
    doc = json.loads(_raw("verified"))
    run = doc["body"]["run"]
    assessment = json.loads(run["assessmentText"])
    assessment["changes"][0]["to"] = 1.9  # claim a different approved value
    run["assessmentText"] = json.dumps(assessment, indent=2)
    doc["integrity"]["bodySha256"] = canonical_sha256(doc["body"])  # attacker re-hashes
    report = verify_evidence(json.dumps(doc).encode())
    status = {c["id"]: c["status"] for c in report["checks"]}
    assert report["integrity"] == "VERIFIED"
    assert status["gate_recompute"] == "fail"
    assert report["overall"] == "FAIL"


def test_forged_history_is_rejected() -> None:
    doc = json.loads(_raw("gate-rejected"))
    doc["body"]["run"]["history"].append(
        {"state": "APPROVED", "at": "2026-10-25T00:00:01Z", "detail": "x"},
    )
    doc["integrity"]["bodySha256"] = canonical_sha256(doc["body"])
    report = verify_evidence(json.dumps(doc).encode())
    assert any(c["id"] == "history" and c["status"] == "fail" for c in report["checks"])


def test_duplicate_keys_and_nan_are_unreadable() -> None:
    assert verify_evidence(b'{"a":1,"a":2}')["integrity"] == "UNREADABLE"
    assert verify_evidence(b'{"a":NaN}')["integrity"] == "UNREADABLE"


def test_cli_exit_codes(tmp_path) -> None:
    script = ROOT / "scripts" / "crystalpilot_verify.py"
    fixture = FIXTURES / "crystalpilot_evidence.verified.offline.json"
    ok = subprocess.run(
        [sys.executable, str(script), str(fixture)], capture_output=True, text=True, check=False,
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "PASS" in ok.stdout
    bad = tmp_path / "bad.json"
    doc = json.loads(_raw("verified"))
    doc["body"]["run"]["scenarioName"] = "edited"
    bad.write_text(json.dumps(doc))
    failed = subprocess.run(
        [sys.executable, str(script), str(bad)], capture_output=True, check=False,
    )
    assert failed.returncode == 2
