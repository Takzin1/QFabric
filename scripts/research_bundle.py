"""Offline, byte-exact research bundle for the CrystalTwinAI/QFabric bridge.

This is a synthetic interoperability audit, NOT scientific replication or
evidence of quantum measurement, hardware control or quantum advantage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from crystaltwin_bridge import MAX_INPUT_BYTES, verify_report

SCHEMA = "ctqf-research-bundle/1"
MAX_MANIFEST_BYTES = 16 * 1024


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(raw: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(raw, object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise TypeError("JSON document must be an object")
    return parsed


def build_bundle(snapshot_bytes: bytes, report_bytes: bytes) -> dict[str, Any]:
    """Validate source/report bytes first, then generate an immutable run card.

    An integrity pass verifies local byte linkage and pre-existing QFabric
    invariants. It does not authenticate an external author or dataset.
    """
    if len(snapshot_bytes) > MAX_INPUT_BYTES or len(report_bytes) > MAX_INPUT_BYTES:
        raise ValueError("snapshot/report exceeds 512 KiB")
    verify_report(snapshot_bytes, report_bytes)
    report = _load_json(report_bytes)
    a, b = _digest(snapshot_bytes), _digest(report_bytes)
    analytics = report["analytics"]
    return {
        "schemaVersion": SCHEMA,
        "kind": "synthetic_offline_interoperability",
        "runId": f"syn-{a[:12]}-{b[:12]}",
        "protocol": {
            "snapshotSchema": "crystaltwin-qfabric-snapshot/1",
            "reportSchema": "qfabric-crystaltwin-report/1",
        },
        "sha256": {"snapshot": a, "report": b},
        "primaryQuestion": "Does the exact-byte offline bridge preserve its declared safety and integrity invariants?",
        "primaryEndpoint": "snapshot_report_link_and_plan_only_invariants",
        "primaryResult": "passes_synthetic_integrity_gates",
        "environment": {"analyticsBackend": analytics["backend"], "shots": analytics["shots"]},
        "integrityChecks": {
            "exactSourceBytes": True,
            "qfabricSemanticInvariants": True,
        },
        "physicalMeasurement": False,
        "hardwareExecuted": False,
        "scientificReplication": False,
    }


def verify_bundle(snapshot_bytes: bytes, report_bytes: bytes, manifest_bytes: bytes) -> dict[str, Any]:
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise ValueError("manifest exceeds 16 KiB")
    stored = _load_json(manifest_bytes)
    expected = build_bundle(snapshot_bytes, report_bytes)
    if stored != expected:
        raise ValueError("manifest differs from independently reconstructed experiment bundle")
    return expected


def _bounded_read(path: Path, maximum: int) -> bytes:
    if path.stat().st_size > maximum:
        raise ValueError(f"{path.name} exceeds byte limit")
    raw = path.read_bytes()
    if len(raw) > maximum:
        raise ValueError(f"{path.name} exceeds byte limit")
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthetic offline research bundle; NO physical measurements.")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--verify", action="store_true", help="verify existing bundle against exact bytes")
    args = parser.parse_args(argv)
    snapshot_bytes = _bounded_read(args.snapshot, MAX_INPUT_BYTES)
    report_bytes = _bounded_read(args.report, MAX_INPUT_BYTES)
    if args.verify:
        verify_bundle(snapshot_bytes, report_bytes, _bounded_read(args.manifest, MAX_MANIFEST_BYTES))
        print("PASS: exact-byte synthetic bridge integrity (not scientific replication)")
    else:
        manifest = build_bundle(snapshot_bytes, report_bytes)
        output = json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        # Do not overwrite an existing run manifest accidentally.
        with args.manifest.open("x", encoding="utf-8") as handle:
            handle.write(output)
        print(f"Created {args.manifest} ({manifest['runId']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
