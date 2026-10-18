"""Fail-closed, dependency-free *metadata* and synthetic-count baselines.

No network, archive extraction, quantum hardware, model execution or measured-data
ingestion occurs. Zenodo metadata alone is never validation of raw measurements.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date
from typing import Any
from urllib.parse import urlsplit

CATALOG_VERSION = "qfabric-quantum-dataset-candidates/1"
COUNTS_VERSION = "qfabric-synthetic-counts/1"
BASELINE_VERSION = "qfabric-count-baseline/1"
MAX_CATALOG_BYTES = 128 * 1024
MAX_COUNTS_BYTES = 64 * 1024
MAX_DATASETS = 100
MAX_GROUPS = 100
MAX_SHOTS = 1_000_000_000
Z_95 = 1.959963984540054
_DATASET_ID = re.compile(r"QRD-[0-9]{3}$")
_DOI = re.compile(r"10\\.[0-9]{4,9}/[^\\s]+$", re.IGNORECASE)
_MD5 = re.compile(r"[0-9a-f]{32}$")
_EXPECTED_DATASET_FIELDS = frozenset({
    "datasetId", "priority", "title", "paperUrl", "paperDoi",
    "recordUrl", "datasetDoi", "filename", "format",
    "publishedMd5", "provenance", "licenseStatus", "licenseIdentifier",
    "unitStatus", "ingestStatus", "rawSha256", "note",
})


def _no_constant(value: str) -> None:
    raise ValueError(f"invalid JSON numeric constant: {value}")


def _unique_object(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _read_json(raw: bytes, *, limit: int) -> dict[str, Any]:
    if not isinstance(raw, bytes):
        raise TypeError("input must be bytes")
    if len(raw) > limit:
        raise ValueError("input exceeds maximum byte length")
    try:
        parsed = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_object,
            parse_constant=_no_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise TypeError("JSON root must be an object")
    return parsed


def _exact_fields(value: Any, expected: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{label} must have exactly the documented fields")
    return value


def _text(value: Any, name: str, limit: int = 400) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
        raise ValueError(f"{name} must be bounded nonempty text")
    return value


def _https_url(value: Any, *, hosts: set[str] | None = None) -> None:
    _text(value, "URL", 500)
    parts = urlsplit(value)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.fragment
        or (hosts is not None and parts.hostname not in hosts)
    ):
        raise ValueError("only approved HTTPS reference URLs are allowed")


def _doi(value: Any, name: str) -> None:
    if not isinstance(value, str) or not _DOI.fullmatch(value):
        raise ValueError(f"{name} must be a DOI")


def validate_catalog(raw: bytes) -> dict[str, Any]:
    """Validate citation candidates only. Cannot promote metadata to measurements."""
    catalog = _read_json(raw, limit=MAX_CATALOG_BYTES)
    _exact_fields(
        catalog, frozenset({"schemaVersion", "reviewedOn", "datasets"}), "catalog"
    )
    if catalog["schemaVersion"] != CATALOG_VERSION:
        raise ValueError("unsupported catalog schema")
    reviewed = _text(catalog["reviewedOn"], "reviewedOn", 10)
    try:
        if date.fromisoformat(reviewed).isoformat() != reviewed:
            raise ValueError("invalid reviewedOn date")
    except ValueError as exc:
        raise ValueError("invalid reviewedOn date") from exc
    datasets = catalog["datasets"]
    if not isinstance(datasets, list) or not 1 <= len(datasets) <= MAX_DATASETS:
        raise ValueError("datasets must contain 1..100 records")
    seen: set[str] = set()
    for data in datasets:
        item = _exact_fields(data, _EXPECTED_DATASET_FIELDS, "dataset")
        key = item["datasetId"]
        if not isinstance(key, str) or not _DATASET_ID.fullmatch(key) or key in seen:
            raise ValueError("datasetId must be unique and of form QRD-000")
        seen.add(key)
        if item["priority"] not in {"P0", "P1", "P2", "P3"}:
            raise ValueError("invalid priority")
        _text(item["title"], "title", 250)
        _https_url(item["paperUrl"])
        if item["paperDoi"] is not None:
            _doi(item["paperDoi"], "paperDoi")
        _https_url(item["recordUrl"], hosts={"zenodo.org"})
        _doi(item["datasetDoi"], "datasetDoi")
        record_id = item["recordUrl"].removeprefix("https://zenodo.org/records/")
        if (
            not re.fullmatch(r"[0-9]+", record_id)
            or item["datasetDoi"] != f"10.5281/zenodo.{record_id}"
        ):
            raise ValueError("Zenodo record URL and version-specific DOI do not match")
        filename = _text(item["filename"], "filename", 255)
        if filename in {".", ".."} or filename.startswith(".") or (
            "/" in filename or "\\" in filename or "\x00" in filename
        ):
            raise ValueError("filename must be a safe basename")
        if item["format"] not in {"csv", "txt", "xlsx", "hdf5", "zip", "tar.gz", "npz"}:
            raise ValueError("unsupported candidate file format")
        checksum = item["publishedMd5"]
        if checksum is not None and (
            not isinstance(checksum, str) or not _MD5.fullmatch(checksum)
        ):
            raise ValueError("publishedMd5 must be null or lowercase MD5 metadata")
        if item["provenance"] not in {
            "measured_claim", "mixed_claim", "simulation_claim"
        }:
            raise ValueError("unsupported record-supplied provenance classification")
        if (
            item["licenseStatus"] != "unverified"
            or item["licenseIdentifier"] is not None
            or item["unitStatus"] != "unverified"
            or item["ingestStatus"] != "not_downloaded"
            or item["rawSha256"] is not None
        ):
            raise ValueError("metadata-only catalog cannot claim file verification")
        _text(item["note"], "note", 500)
    return catalog


def _integer(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{field} must be integer between {minimum} and {maximum}")
    return value


def _wilson(k: int, n: int) -> tuple[float, float]:
    """Binomial Wilson 95% CI, valid as a *descriptive* computation only."""
    p = k / n
    z2 = Z_95 * Z_95
    den = 1 + z2 / n
    center = (p + z2 / (2 * n)) / den
    half = Z_95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / den
    return max(0.0, center - half), min(1.0, center + half)


def compute_synthetic_count_baseline(raw: bytes) -> dict[str, Any]:
    """Calculate a transparent synthetic binomial reference, never real QEC."""
    doc = _read_json(raw, limit=MAX_COUNTS_BYTES)
    _exact_fields(
        doc, frozenset({"schemaVersion", "kind", "groups"}), "count fixture"
    )
    if doc["schemaVersion"] != COUNTS_VERSION or doc["kind"] != "synthetic_fixture":
        raise ValueError("only explicitly synthetic count fixtures are supported")
    groups = doc["groups"]
    if not isinstance(groups, list) or not 1 <= len(groups) <= MAX_GROUPS:
        raise ValueError("groups must contain 1..100 entries")
    names: set[str] = set()
    output = []
    for group in groups:
        g = _exact_fields(group, frozenset({"name", "shots", "errors"}), "group")
        name = _text(g["name"], "group.name", 80)
        if name in names:
            raise ValueError("duplicate group names")
        names.add(name)
        n = _integer(g["shots"], "shots", 1, MAX_SHOTS)
        k = _integer(g["errors"], "errors", 0, n)
        low, high = _wilson(k, n)
        output.append({
            "name": name, "shots": n, "errors": k,
            "errorRate": k / n, "wilson95Lower": low, "wilson95Upper": high,
        })
    return {
        "schemaVersion": BASELINE_VERSION,
        "kind": "synthetic_binomial_reference",
        "inputSha256": hashlib.sha256(raw).hexdigest(),
        "dataProvenance": "synthetic_fixture",
        "hardwareExecuted": False,
        "measurementVerified": False,
        "confidenceIntervalMethod": "Wilson score, nominal 95%, z=1.959963984540054",
        "assumptions": "Independent Bernoulli trials; not established for correlated QEC data.",
        "results": output,
    }
