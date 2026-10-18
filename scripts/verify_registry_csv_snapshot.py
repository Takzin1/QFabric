"""Fail-closed verification of the QFabric workbook's nine CSV value snapshots.

This validates exported metadata against versioned JSON source catalogs. It
does NOT establish scientific reproduction, original-file authenticity or
spreadsheet formula equivalence. No downloads or QPU calls occur.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = Path("data/spreadsheets/qfabric_registry_2026-10-19")
SCHEMA = "qfabric-spreadsheet-registry-export/1"
EXPECTED_ROWS = {
    "Dashboard": 31,
    "Pinned_Candidates": 16,
    "New_Source_Leads": 8,
    "Artifact_Leads": 13,
    "AI_Benchmark": 2,
    "Verification_Queue": 29,
    "Normalization_Map": 28,
    "Action_Plan": 11,
    "Guide": 25,
}
EXPECTED_COLUMNS = {
    "Dashboard": 7,
    "Pinned_Candidates": 19,
    "New_Source_Leads": 14,
    "Artifact_Leads": 14,
    "AI_Benchmark": 16,
    "Verification_Queue": 22,
    "Normalization_Map": 18,
    "Action_Plan": 8,
    "Guide": 4,
}
TABLES = frozenset(EXPECTED_ROWS) - {"Dashboard", "Guide"}


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def _get_csv(root: Path, name: str) -> list[list[str]]:
    path = root / EXPORT_DIR / f"{name}.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle, strict=True))
    _require(len(rows) == EXPECTED_ROWS[name], f"{name}: row count changed")
    _require(
        all(len(row) == EXPECTED_COLUMNS[name] for row in rows),
        f"{name}: malformed column count",
    )
    _require(
        all(not re.match(r"^[=+@]", value) for row in rows for value in row),
        f"{name}: unsafe literal spreadsheet formula prefix",
    )
    return rows


def _records(root: Path, path: str, key: str) -> list[dict[str, Any]]:
    with (root / path).open(encoding="utf-8") as fh:
        doc = json.load(fh)
    records = doc[key]
    _require(isinstance(records, list), f"{path} source list malformed")
    return records


def _row_dicts(rows: list[list[str]], name: str) -> list[dict[str, str]]:
    headers = rows[0]
    _require(all(headers) and len(set(headers)) == len(headers), f"{name}: header changed")
    return [dict(zip(headers, row, strict=True)) for row in rows[1:]]


def _same(row: dict[str, str], label: str, source: Any, owner: str) -> None:
    expected = "" if source is None else str(source)
    if label == "Source note":
        # Spreadsheet display strips Markdown emphasis from the QRI-006 note.
        # Do not mutate either source JSON or the exported Excel cell value.
        expected = expected.replace("*", "")
    _require(row[label] == expected, f"{owner}: field {label!r} differs from GitHub JSON")


def validate_snapshot(root: Path = ROOT) -> dict[str, Any]:
    with (root / EXPORT_DIR / "export_manifest.json").open(encoding="utf-8") as fh:
        manifest = json.load(fh)
    _require(manifest["schemaVersion"] == SCHEMA, "unsupported snapshot schema")
    _require(
        manifest["sourceWorkbookSha256"] == (
            "624c993cf69127793459f6d030a94077d6b2f8567510f4d2936e2c59023933f7"
        ),
        "source workbook SHA256 provenance changed unexpectedly",
    )
    _require(manifest["sourceWorkbookSizeBytes"] == 42441, "source workbook size changed")
    _require(
        manifest["xlsxBinaryCommitted"] is False
        and manifest["formulasPreserved"] is False
        and manifest["stylesPreserved"] is False,
        "value-only snapshot cannot claim physical workbook or formulas",
    )
    _require(
        manifest["datasetLicensesVerified"] == 0
        and manifest["measurementsValidated"] == 0,
        "candidate spreadsheet is not scientific evidence validation",
    )
    sheets = manifest["sheets"]
    _require(
        len(sheets) == 9 and {s["name"] for s in sheets} == set(EXPECTED_ROWS),
        "nine exported sheets must be present exactly once",
    )
    for sheet in sheets:
        name = sheet["name"]
        _require(
            sheet["path"] == str(EXPORT_DIR / f"{name}.csv")
            and sheet["rows"] == EXPECTED_ROWS[name]
            and sheet["columns"] == EXPECTED_COLUMNS[name]
            and sheet["headerOrigin"] == (
                "Excel row 4" if name in TABLES else "Excel row 1"
            ),
            f"{name}: manifest layout mismatch",
        )
    tables = {name: _get_csv(root, name) for name in EXPECTED_ROWS}
    pinned = _records(root, "data/quantum_dataset_candidates.json", "datasets")
    leads = _records(root, "data/quantum_source_intake.json", "sources")
    ai = _records(root, "data/quantum_ai_eval_candidates.json", "datasets")

    pinned_rows = _row_dicts(tables["Pinned_Candidates"], "Pinned_Candidates")
    _require(len(pinned_rows) == len(pinned) == 15, "pinned dataset count mismatch")
    for row, source in zip(pinned_rows, pinned, strict=True):
        for label, key in (
            ("Dataset ID", "datasetId"),
            ("Priority", "priority"),
            ("Research title", "title"),
            ("Paper URL", "paperUrl"),
            ("Paper DOI", "paperDoi"),
            ("Pinned Zenodo record", "recordUrl"),
            ("Dataset DOI", "datasetDoi"),
            ("Source filename", "filename"),
            ("File format", "format"),
            ("Provider MD5 (claim)", "publishedMd5"),
            ("Source provenance (claim)", "provenance"),
            ("License review", "licenseStatus"),
            ("License identifier", "licenseIdentifier"),
            ("Units review", "unitStatus"),
            ("Download status", "ingestStatus"),
            ("Local SHA256", "rawSha256"),
            ("Source note", "note"),
        ):
            _same(row, label, source[key], source["datasetId"])

    lead_rows = _row_dicts(tables["New_Source_Leads"], "New_Source_Leads")
    _require(len(lead_rows) == len(leads) == 7, "source lead count mismatch")
    artifact_ids: set[str] = set()
    for row, source in zip(lead_rows, leads, strict=True):
        for label, key in (
            ("Source ID", "sourceId"),
            ("Research title", "title"),
            ("Pinned Zenodo URL", "recordUrl"),
            ("Record ID", "recordId"),
            ("Paper URL", "paperUrl"),
            ("Research lane", "track"),
            ("Source origin (claim)", "originClaim"),
            ("License review", "licenseStatus"),
            ("License ID", "licenseIdentifier"),
            ("Review status", "reviewStatus"),
            ("Source note", "note"),
        ):
            _same(row, label, source[key], source["sourceId"])
        _same(
            row, "Hardware families", ", ".join(source["hardwareFamilies"]), source["sourceId"]
        )
        _same(row, "Artifact count", len(source["artifacts"]), source["sourceId"])
        for n in range(1, len(source["artifacts"]) + 1):
            artifact_ids.add(f"{source['sourceId']}-A{n:02d}")

    artifact_rows = _row_dicts(tables["Artifact_Leads"], "Artifact_Leads")
    _require(len(artifact_rows) == len(artifact_ids) == 12, "artifact count mismatch")
    for row in artifact_rows:
        _require(row["Artifact ID"] in artifact_ids, "unrecognized artifact ID")
        _require(row["Download status"] == "not_downloaded", "false artifact download claim")
        _require(row["Source unit"] == "" and row["Raw SHA256"] == "", "invented units/hash")
        _require(
            row["License review"] == "unverified"
            and row["Review state"] == "source_lead_only",
            "unsupported artifact scientific approval",
        )
    _require(
        {row["Artifact ID"] for row in artifact_rows} == artifact_ids,
        "artifact ID set mismatch",
    )
    for source in leads:
        for i, artifact in enumerate(source["artifacts"], 1):
            ident = f"{source['sourceId']}-A{i:02d}"
            row = next(item for item in artifact_rows if item["Artifact ID"] == ident)
            for label, value in (
                ("Source ID", source["sourceId"]),
                ("Source title", source["title"]),
                ("Pinned record URL", source["recordUrl"]),
                ("Candidate artifact / description", artifact["label"]),
                ("Original filename", artifact["filename"]),
                ("Format", artifact["format"]),
                ("File role", artifact["role"]),
                ("Source origin (claim)", artifact["dataOrigin"]),
            ):
                _same(row, label, value, ident)

    ai_rows = _row_dicts(tables["AI_Benchmark"], "AI_Benchmark")
    _require(len(ai_rows) == len(ai) == 1, "AI benchmark count mismatch")
    ai_row = ai_rows[0]
    _same(ai_row, "AI ID", ai[0]["candidateId"], "QAE-001")
    _same(ai_row, "Dataset URL", ai[0]["datasetUrl"], "QAE-001")
    _same(ai_row, "Evaluation code", ai[0]["evaluationCodeUrl"], "QAE-001")
    _same(ai_row, "Download status", ai[0]["downloadStatus"], "QAE-001")
    _require(
        ai_row["Model evaluated"] == "False" and ai_row["Benchmark score"] == "",
        "AI inference was not run",
    )

    queue = _row_dicts(tables["Verification_Queue"], "Verification_Queue")
    expected_ids = (
        {d["datasetId"] for d in pinned} | artifact_ids | {d["candidateId"] for d in ai}
    )
    _require(
        len(queue) == len(expected_ids) == 28
        and {row["Evidence ID"] for row in queue} == expected_ids,
        "verification queue references do not cover source records",
    )
    for row in queue:
        _require(
            all(row[field] == "Not started" for field in (
                "Record cited", "License checked", "Original file obtained",
                "Local hash compared", "Source units mapped", "Methods documented",
                "Independent calculation",
            )),
            "spreadsheet falsely reports completed scientific evidence",
        )
        _require(
            row["Sheet review gate"] == "HOLD — incomplete evidence",
            "spreadsheet review gate must remain on HOLD",
        )

    mapping = _row_dicts(tables["Normalization_Map"], "Normalization_Map")
    _require(len(mapping) == 27, "normalization mapping count mismatch")
    _require(
        all(row["Map status"] == "Unmapped" for row in mapping),
        "uninspected source units cannot be mapped",
    )
    plan = _row_dicts(tables["Action_Plan"], "Action_Plan")
    _require(
        len(plan) == 10 and len({r["Task ID"] for r in plan}) == 10,
        "action plan entries must be distinct",
    )
    _require(tables["Dashboard"][0][0].startswith("QFABRIC /"), "dashboard header absent")
    _require(tables["Guide"][0][0].startswith("USAGE /"), "guide header absent")

    return {
        "schemaVersion": SCHEMA,
        "workbookSha256": manifest["sourceWorkbookSha256"],
        "sheets": len(sheets),
        "pinnedCandidates": len(pinned),
        "sourceLeads": len(leads),
        "artifactLeads": len(artifact_ids),
        "aiBenchmarkCandidates": len(ai),
        "verificationQueue": len(queue),
        "unitMappings": len(mapping),
        "actionTasks": len(plan),
        "verifiedMeasuredDatasets": 0,
        "binaryWorkbookCommitted": False,
        "status": "source-aligned cell-value CSV snapshot; no measurement verification",
    }


if __name__ == "__main__":
    print(json.dumps(validate_snapshot(), indent=2, ensure_ascii=False))
