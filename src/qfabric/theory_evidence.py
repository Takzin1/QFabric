"""Offline-only validation of curated quantum-theory reference metadata.

This registry is a bibliography, not an experimental dataset, executable
quantum circuit, physical calibration or endorsement of CrystalTwinAI physics.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "qfabric-quantum-theory-evidence/1"
MAX_BYTES = 128 * 1024
DOI = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\Z")
SHA_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
TOP_KEYS = frozenset({
    "schemaVersion", "kind", "compiledOn", "ownerRepository",
    "bibliographyScope", "citationMethod", "citationDefaultSourceUrl",
    "ingestionPolicy", "integrationBoundary", "entries",
})
ITEM_KEYS = frozenset({
    "id", "title", "authors", "year", "doi", "primaryUrl", "publicationType",
    "role", "citationSnapshot", "supportedClaim", "researchQuestion",
    "limitations", "qfabricUse", "crystalTwinUse", "reproductionStatus",
})
CITATION_KEYS = frozenset({"count", "sourceUrl", "observedOn", "metric", "notes"})


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for key, value in pairs:
        if key in data:
            raise ValueError(f"duplicate key: {key}")
        data[key] = value
    return data


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite JSON constant: {value}")


def _fields(value: Any, fields: frozenset[str], at: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{at}: unexpected fields")
    return value


def _text(value: Any, at: str, limit: int = 800) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{at}: invalid bounded text")
    return value


def validate_registry(raw: bytes) -> dict[str, Any]:
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError("registry must be bounded UTF-8 bytes")
    try:
        doc = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("registry is not valid UTF-8 JSON") from exc
    obj = _fields(doc, TOP_KEYS, "registry")
    if obj["schemaVersion"] != SCHEMA or obj["kind"] != "curated_public_literature_registry":
        raise ValueError("unsupported evidence registry version")
    if obj["ownerRepository"] != "Takzin1/QFabric":
        raise ValueError("unexpected publisher")
    if not isinstance(obj["compiledOn"], str) or not SHA_DATE.fullmatch(obj["compiledOn"]):
        raise ValueError("invalid compilation date")
    for field in ("bibliographyScope", "citationMethod", "ingestionPolicy",
                  "integrationBoundary"):
        _text(obj[field], field, 1600)
    if obj["citationDefaultSourceUrl"] != "https://openalex.org/topics/T10682":
        raise ValueError("unexpected citation source")
    entries = obj["entries"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 100:
        raise ValueError("registry requires 1 to 100 papers")
    seen_ids: set[str] = set()
    seen_dois: set[str] = set()
    for index, value in enumerate(entries):
        at = f"entries[{index}]"
        item = _fields(value, ITEM_KEYS, at)
        for name in ("id", "title", "authors", "doi", "role", "supportedClaim",
                     "researchQuestion", "limitations"):
            _text(item[name], at + "." + name)
        if item["id"] in seen_ids or item["doi"].lower() in seen_dois:
            raise ValueError("duplicate paper ID or DOI")
        seen_ids.add(item["id"])
        seen_dois.add(item["doi"].lower())
        if not DOI.fullmatch(item["doi"]) or item["primaryUrl"] != (
            "https://doi.org/" + item["doi"]
        ):
            raise ValueError(f"{at}: DOI and original URL disagree")
        if type(item["year"]) is not int or not 1980 <= item["year"] <= 2026:
            raise ValueError(f"{at}: invalid publication year")
        if item["publicationType"] not in {
            "conference_paper", "journal_article", "review_article",
        }:
            raise ValueError(f"{at}: invalid paper category")
        if item["qfabricUse"] != "background_or_hypothesis_only" or (
            item["crystalTwinUse"] != "context_only_no_engine_calibration"
        ) or item["reproductionStatus"] != "not_reproduced_in_either_repository":
            raise ValueError(f"{at}: unsupported scientific/experimental claims")
        cited = item["citationSnapshot"]
        if cited is not None:
            cite = _fields(cited, CITATION_KEYS, at + ".citationSnapshot")
            if type(cite["count"]) is not int or cite["count"] < 0:
                raise ValueError(f"{at}: citation count must be a nonnegative integer")
            if not isinstance(cite["observedOn"], str) or not SHA_DATE.fullmatch(
                cite["observedOn"]
            ):
                raise ValueError(f"{at}: invalid citation observation date")
            if cite["metric"] != "displayed_citations":
                raise ValueError(f"{at}: unexpected citation metric")
            _text(cite["notes"], at + ".citationSnapshot.notes")
            if cite["sourceUrl"] not in {
                "https://openalex.org/topics/T10682",
                "https://www.nature.com/articles/s41586-024-08449-y",
                "https://www.nature.com/articles/s41567-026-03220-8",
            }:
                raise ValueError(f"{at}: unknown citation-count source")
    return obj


def load_registry(path: Path) -> dict[str, Any]:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("registry too large")
    return validate_registry(path.read_bytes())
