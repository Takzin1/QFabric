"""Source-lead structure regressions: no fabricated raw data or silent promotion."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from qfabric.source_intake import INTAKE_VERSION, summarize_source_intake, validate_source_intake

ROOT = Path(__file__).resolve().parents[1]
RAW = (ROOT / "data/quantum_source_intake.json").read_bytes()
PINNED = (ROOT / "data/quantum_dataset_candidates.json").read_bytes()
SPEC = importlib.util.spec_from_file_location(
    "quantum_dataset_cli_intake", ROOT / "scripts/quantum_dataset_baseline.py"
)
assert SPEC and SPEC.loader
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


def _encoded(doc: dict) -> bytes:
    return json.dumps(doc, ensure_ascii=False).encode("utf-8")


def test_intake_structures_six_datasets_and_one_software_tool() -> None:
    doc = validate_source_intake(RAW, pinned_catalog_raw=PINNED)
    assert doc["schemaVersion"] == INTAKE_VERSION
    assert len(doc["sources"]) == 7
    assert {x["sourceId"] for x in doc["sources"]} == {
        f"QRI-{i:03d}" for i in range(1, 8)
    }
    assert len([x for x in doc["sources"] if x["track"] == "software_generator"]) == 1
    assert len([x for x in doc["sources"] if x["track"] != "software_generator"]) == 6
    report = summarize_source_intake(RAW, pinned_catalog_raw=PINNED)
    assert report["intakeSources"] == 7
    assert report["artifactLeads"] == 12
    assert report["knownBasenames"] == 7
    assert report["unknownBasenames"] == 5
    assert report["downloadedArtifacts"] == 0
    assert report["validatedMeasurements"] == 0
    assert report["reproducedExperiments"] == 0
    assert report["hardwareExecuted"] is False
    assert report["softwareExecuted"] is False


def test_artifacts_keep_file_level_provenance_and_unknown_units() -> None:
    doc = validate_source_intake(RAW, pinned_catalog_raw=PINNED)
    files = [f for x in doc["sources"] for f in x["artifacts"]]
    assert all(f["units"] is None and f["rawSha256"] is None for f in files)
    assert all(f["downloadStatus"] == "not_downloaded" for f in files)
    assert all(x["licenseStatus"] == "unverified" for x in doc["sources"])
    assert all(x["licenseIdentifier"] is None for x in doc["sources"])
    assert all(x["reviewStatus"] == "source_lead_only" for x in doc["sources"])
    software = doc["sources"][-1]
    assert software["track"] == "software_generator"
    assert all(f["role"] == "software_artifact" for f in software["artifacts"])
    assert all(f["dataOrigin"] == "tool_only" for f in software["artifacts"])


@pytest.mark.parametrize(
    ("source_index", "field", "replacement"),
    [
        (0, "recordId", "1"),
        (0, "recordUrl", "http://zenodo.org/records/21775462"),
        (0, "recordUrl", "https://zenodo.org/records/21775462?download=1"),
        (0, "sourceId", "QRD-019"),
        (0, "licenseStatus", "verified"),
        (0, "licenseIdentifier", "CC-BY-4.0"),
        (0, "reviewStatus", "independently_reproduced"),
        (0, "hardwareFamilies", ["superconducting"]),
        (0, "hardwareFamilies", ["simulation_only", "superconducting"]),
        (0, "hardwareFamilies", ["superconducting", "superconducting"]),
        (0, "paperUrl", "http://doi.org/10.1038/example"),
        (0, "paperUrl", "https://malicious.example/10.1038/example"),
        (3, "originClaim", "measured_claim"),
        (6, "originClaim", "measured_claim"),
        (6, "track", "noise_time_series"),
    ],
)
def test_source_unverified_status_and_tracks_cannot_be_promoted(
    source_index: int, field: str, replacement: object
) -> None:
    doc = json.loads(RAW)
    doc["sources"][source_index][field] = replacement
    with pytest.raises((ValueError, TypeError)):
        validate_source_intake(_encoded(doc), pinned_catalog_raw=PINNED)


@pytest.mark.parametrize(
    ("source_index", "artifact_index", "field", "replacement"),
    [
        (1, 0, "filename", "../Fig3c.xlsx"),
        (1, 0, "filename", "Fig3c.csv"),
        (1, 0, "filename", "fig\n.xlsx"),
        (1, 0, "filename", "/tmp/Fig3c.xlsx"),
        (1, 0, "rawSha256", "a" * 64),
        (1, 0, "units", "microseconds"),
        (1, 0, "downloadStatus", "downloaded"),
        (1, 0, "role", "software_artifact"),
        (3, 0, "dataOrigin", "measured_claim"),
        (5, 0, "dataOrigin", "measured_claim"),
        (6, 0, "role", "processed_figure"),
        (6, 0, "dataOrigin", "simulation_claim"),
    ],
)
def test_artifact_metadata_cannot_be_claimed_verified(
    source_index: int, artifact_index: int, field: str, replacement: object
) -> None:
    doc = json.loads(RAW)
    doc["sources"][source_index]["artifacts"][artifact_index][field] = replacement
    with pytest.raises((ValueError, TypeError)):
        validate_source_intake(_encoded(doc), pinned_catalog_raw=PINNED)


def test_duplicate_records_and_identifiers_refused() -> None:
    doc = json.loads(RAW)
    doc["sources"][1]["sourceId"] = doc["sources"][0]["sourceId"]
    with pytest.raises(ValueError, match="unique"):
        validate_source_intake(_encoded(doc), pinned_catalog_raw=PINNED)
    doc = json.loads(RAW)
    doc["sources"][1]["recordUrl"] = doc["sources"][0]["recordUrl"]
    doc["sources"][1]["recordId"] = doc["sources"][0]["recordId"]
    with pytest.raises(ValueError, match="duplicated"):
        validate_source_intake(_encoded(doc), pinned_catalog_raw=PINNED)
    doc = json.loads(RAW)
    doc["sources"][0]["recordUrl"] = "https://zenodo.org/records/15364358"
    doc["sources"][0]["recordId"] = "15364358"
    with pytest.raises(ValueError, match="duplicated"):
        validate_source_intake(_encoded(doc), pinned_catalog_raw=PINNED)


def test_duplicate_artifact_file_and_unexpected_fields_rejected() -> None:
    doc = json.loads(RAW)
    doc["sources"][1]["artifacts"][1]["filename"] = "Fig3c.xlsx"
    with pytest.raises(ValueError, match="duplicate"):
        validate_source_intake(_encoded(doc))
    doc = json.loads(RAW)
    doc["sources"][0]["artifacts"][0]["validated"] = True
    with pytest.raises(ValueError, match="fields"):
        validate_source_intake(_encoded(doc))


def test_json_ambiguity_overflow_and_limit_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        validate_source_intake(b'{"schemaVersion":1,"schemaVersion":2}')
    with pytest.raises(ValueError):
        validate_source_intake(b'{"x": NaN}')
    with pytest.raises(ValueError):
        validate_source_intake(b'{"x": 1e309}')
    with pytest.raises(ValueError):
        validate_source_intake(b"x" * (128 * 1024 + 1))


def test_cli_validates_both_catalogs_and_reports_only_leads(capsys) -> None:
    assert cli.main([
        "validate-intake", str(ROOT / "data/quantum_source_intake.json"),
        "--catalog", str(ROOT / "data/quantum_dataset_candidates.json"),
    ]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["intakeSources"] == 7
    assert report["validatedMeasurements"] == 0
    assert report["downloadedArtifacts"] == 0
    assert report["hardwareExecuted"] is False


def test_cli_missing_catalog_or_bad_intake_refuses(tmp_path: Path) -> None:
    altered = json.loads(RAW)
    altered["sources"][0]["licenseStatus"] = "verified"
    data = tmp_path / "intake.json"
    data.write_bytes(_encoded(altered))
    assert cli.main([
        "validate-intake", str(data),
        "--catalog", str(ROOT / "data/quantum_dataset_candidates.json"),
    ]) == 1
