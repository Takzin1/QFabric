"""Regression tests: workbook-derived CSV is a source-aligned, unverified snapshot."""

from __future__ import annotations

import csv
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_registry_snapshot", ROOT / "scripts/verify_registry_csv_snapshot.py"
)
assert SPEC and SPEC.loader
registry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(registry)


def _clone_snapshot(tmp_path: Path) -> Path:
    for name in (
        "quantum_dataset_candidates.json",
        "quantum_source_intake.json",
        "quantum_ai_eval_candidates.json",
    ):
        folder = tmp_path / "data"
        folder.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / "data" / name, folder / name)
    target = tmp_path / registry.EXPORT_DIR
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / registry.EXPORT_DIR, target)
    return tmp_path


def test_snapshot_matches_all_three_github_catalogs() -> None:
    result = registry.validate_snapshot()
    assert result["sheets"] == 9
    assert result["pinnedCandidates"] == 15
    assert result["sourceLeads"] == 7
    assert result["artifactLeads"] == 12
    assert result["aiBenchmarkCandidates"] == 1
    assert result["verificationQueue"] == 28
    assert result["unitMappings"] == 27
    assert result["actionTasks"] == 10
    assert result["verifiedMeasuredDatasets"] == 0
    assert result["binaryWorkbookCommitted"] is False


def test_snapshot_rejects_forged_download_flag(tmp_path: Path) -> None:
    root = _clone_snapshot(tmp_path)
    path = root / registry.EXPORT_DIR / "Pinned_Candidates.csv"
    rows = list(csv.reader(path.open(encoding="utf-8", newline="")))
    download_col = rows[0].index("Download status")
    rows[1][download_col] = "verified"
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    with pytest.raises(ValueError, match="Download status"):
        registry.validate_snapshot(root)


def test_snapshot_rejects_evidence_promotion(tmp_path: Path) -> None:
    root = _clone_snapshot(tmp_path)
    path = root / registry.EXPORT_DIR / "Verification_Queue.csv"
    rows = list(csv.reader(path.open(encoding="utf-8", newline="")))
    rows[1][rows[0].index("Record cited")] = "Evidence recorded"
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    with pytest.raises(ValueError, match="falsely reports"):
        registry.validate_snapshot(root)


def test_snapshot_rejects_missing_rows(tmp_path: Path) -> None:
    root = _clone_snapshot(tmp_path)
    path = root / registry.EXPORT_DIR / "Artifact_Leads.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="row count changed"):
        registry.validate_snapshot(root)


def test_manifest_cannot_claim_binary_xlsx_was_uploaded(tmp_path: Path) -> None:
    root = _clone_snapshot(tmp_path)
    path = root / registry.EXPORT_DIR / "export_manifest.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["xlsxBinaryCommitted"] = True
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="value-only snapshot"):
        registry.validate_snapshot(root)
