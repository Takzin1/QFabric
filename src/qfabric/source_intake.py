"""Fail-closed, source-only intake for quantum research data and software leads.

This module structures *leads*, not downloaded or verified measurements.
It never performs network I/O, reads archives, runs author code, or dispatches QPU calls.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from typing import Any
from urllib.parse import urlsplit

from qfabric.dataset_baseline import (
    MAX_CATALOG_BYTES,
    _exact_fields,
    _https_url,
    _read_json,
    _text,
    validate_catalog,
)

INTAKE_VERSION = "qfabric-quantum-source-intake/1"
MAX_SOURCES = 50
MAX_ARTIFACTS_PER_SOURCE = 10
_SOURCE_FIELDS = frozenset({
    "sourceId", "title", "recordUrl", "recordId", "paperUrl",
    "track", "originClaim", "hardwareFamilies", "licenseStatus",
    "licenseIdentifier", "reviewStatus", "artifacts", "note",
})
_ARTIFACT_FIELDS = frozenset({
    "label", "filename", "format", "role", "dataOrigin",
    "units", "rawSha256", "downloadStatus",
})
_TRACKS = frozenset({
    "cross_vendor_calibration", "processed_experimental_figures",
    "noise_time_series", "decoder_simulation", "mixed_research_data",
    "software_generator",
})
_ORIGINS = frozenset({"measured_claim", "mixed_claim", "simulation_claim", "tool_only"})
_FILE_ORIGINS = _ORIGINS | {"unknown"}
_HARDWARE = frozenset({
    "superconducting", "trapped_ion", "neutral_atom", "photonic",
    "semiconductor_spin", "simulation_only", "unknown",
})
_ROLES = frozenset({
    "calibration_snapshot", "processed_figure", "simulation_output",
    "analysis_code", "software_artifact",
})
_FORMATS = {
    "csv": (".csv",), "json": (".json",), "xlsx": (".xlsx",),
    "hdf5": (".h5", ".hdf5"), "txt": (".txt",), "zip": (".zip",),
}
_ID = re.compile(r"QRI-[0-9]{3}$")
_RECORD = re.compile(r"https://zenodo\.org/records/([1-9][0-9]*)$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _safe_filename(value: Any, format_name: str) -> None:
    if value is None:  # Unknown original filename, never fabricate one.
        return
    filename = _text(value, "artifact.filename", 255)
    if (
        filename.startswith(".") or filename in {".", ".."}
        or "/" in filename or "\\" in filename or _CONTROL.search(filename)
        or not filename.lower().endswith(_FORMATS[format_name])
    ):
        raise ValueError("artifact filename must be a safe basename matching its format")


def _source_paper(value: Any) -> None:
    if value is None:
        return
    _https_url(value)
    parts = urlsplit(value)
    if (
        parts.hostname not in {"doi.org", "arxiv.org"}
        or parts.port is not None
        or parts.query
        or not parts.path.strip("/")
    ):
        raise ValueError("paper source must be a direct HTTPS DOI/arXiv reference")


def _validate_artifact(data: Any, origin_claim: str) -> None:
    item = _exact_fields(data, _ARTIFACT_FIELDS, "artifact")
    _text(item["label"], "artifact.label", 180)
    fmt = item["format"]
    if not isinstance(fmt, str) or fmt not in _FORMATS:
        raise ValueError("unsupported artifact format")
    _safe_filename(item["filename"], fmt)
    if item["role"] not in _ROLES or item["dataOrigin"] not in _FILE_ORIGINS:
        raise ValueError("unsupported artifact role or origin")
    if (
        item["units"] is not None
        or item["rawSha256"] is not None
        or item["downloadStatus"] != "not_downloaded"
    ):
        raise ValueError("uninspected artifact cannot claim units, hashes or download")
    if item["role"] in {"analysis_code", "software_artifact"} and (
        item["dataOrigin"] == "measured_claim"
    ):
        raise ValueError("code artifacts must not be marked as measurements")
    if origin_claim == "simulation_claim" and item["dataOrigin"] != "simulation_claim":
        raise ValueError("simulation-only source cannot contain measurement claims")
    if origin_claim == "tool_only" and (
        item["role"] != "software_artifact" or item["dataOrigin"] != "tool_only"
    ):
        raise ValueError("software-only leads must never be treated as measurement data")
    if item["role"] == "software_artifact" and origin_claim != "tool_only":
        raise ValueError("software artifact must be in a separate software-only lane")


def validate_source_intake(
    raw: bytes, *, pinned_catalog_raw: bytes | None = None
) -> dict[str, Any]:
    """Validate metadata, classification and duplication without promoting evidence."""
    doc = _read_json(raw, limit=MAX_CATALOG_BYTES)
    _exact_fields(doc, frozenset({"schemaVersion", "reviewedOn", "sources"}), "intake")
    if doc["schemaVersion"] != INTAKE_VERSION:
        raise ValueError("unsupported source-intake schema")
    reviewed = _text(doc["reviewedOn"], "reviewedOn", 10)
    try:
        if date.fromisoformat(reviewed).isoformat() != reviewed:
            raise ValueError("invalid reviewedOn date")
    except ValueError as exc:
        raise ValueError("invalid reviewedOn date") from exc
    sources = doc["sources"]
    if not isinstance(sources, list) or not 1 <= len(sources) <= MAX_SOURCES:
        raise ValueError("source intake must have 1..50 leads")

    existing_records: set[str] = set()
    if pinned_catalog_raw is not None:
        pinned = validate_catalog(pinned_catalog_raw)
        existing_records = {v["recordUrl"] for v in pinned["datasets"]}
    seen_ids: set[str] = set()
    seen_records: set[str] = set()
    for source in sources:
        entry = _exact_fields(source, _SOURCE_FIELDS, "intake source")
        ident = entry["sourceId"]
        if not isinstance(ident, str) or not _ID.fullmatch(ident) or ident in seen_ids:
            raise ValueError("sourceId must be a unique QRI-### identifier")
        seen_ids.add(ident)
        _text(entry["title"], "source title", 250)
        url = entry["recordUrl"]
        if not isinstance(url, str):
            raise TypeError("recordUrl must be a pinned Zenodo HTTPS record")
        match = _RECORD.fullmatch(url)
        if match is None or entry["recordId"] != match.group(1):
            raise ValueError("pinned Zenodo record and recordId must match exactly")
        if url in seen_records or url in existing_records:
            raise ValueError("source record is duplicated in intake or original catalog")
        seen_records.add(url)
        _source_paper(entry["paperUrl"])
        track, origin = entry["track"], entry["originClaim"]
        if track not in _TRACKS or origin not in _ORIGINS:
            raise ValueError("invalid research track or source provenance")
        families = entry["hardwareFamilies"]
        if (
            not isinstance(families, list) or not 1 <= len(families) <= 8
            or any(not isinstance(x, str) or x not in _HARDWARE for x in families)
            or len(set(families)) != len(families)
        ):
            raise ValueError("invalid or duplicate hardware family")
        if "simulation_only" in families and len(families) > 1:
            raise ValueError("simulation_only cannot be mixed with physical device types")
        if track == "software_generator" and origin != "tool_only":
            raise ValueError("software tool must use tool_only origin")
        if origin == "tool_only" and track != "software_generator":
            raise ValueError("tool_only provenance requires software_generator lane")
        if track == "decoder_simulation" and origin != "simulation_claim":
            raise ValueError("decoder simulation cannot claim measured source origin")
        if track == "cross_vendor_calibration" and len(families) < 2:
            raise ValueError("cross-platform lead must retain multiple hardware families")
        if (
            entry["licenseStatus"] != "unverified"
            or entry["licenseIdentifier"] is not None
            or entry["reviewStatus"] != "source_lead_only"
        ):
            raise ValueError("source-lead intake may not claim license or review approval")
        _text(entry["note"], "source note", 500)
        artifacts = entry["artifacts"]
        if not isinstance(artifacts, list) or not 1 <= len(artifacts) <= MAX_ARTIFACTS_PER_SOURCE:
            raise ValueError("each source must list 1..10 artifact leads")
        names: set[str] = set()
        for artifact in artifacts:
            _validate_artifact(artifact, origin)
            name = artifact["filename"]
            if name is not None:
                if name in names:
                    raise ValueError("duplicate source artifact filename")
                names.add(name)
    return doc


def summarize_source_intake(
    raw: bytes, *, pinned_catalog_raw: bytes | None = None
) -> dict[str, Any]:
    """Machine-readable status: metadata validated, measurements never promoted."""
    doc = validate_source_intake(raw, pinned_catalog_raw=pinned_catalog_raw)
    groups = Counter(s["track"] for s in doc["sources"])
    artifacts = [a for src in doc["sources"] for a in src["artifacts"]]
    return {
        "schemaVersion": INTAKE_VERSION,
        "intakeSources": len(doc["sources"]),
        "artifactLeads": len(artifacts),
        "knownBasenames": sum(a["filename"] is not None for a in artifacts),
        "unknownBasenames": sum(a["filename"] is None for a in artifacts),
        "sourcesByTrack": dict(sorted(groups.items())),
        "downloadedArtifacts": 0,
        "verifiedLicenses": 0,
        "validatedMeasurements": 0,
        "reproducedExperiments": 0,
        "softwareExecuted": False,
        "hardwareExecuted": False,
    }
