"""Offline checks for a research-data catalog and a synthetic count baseline.

Never downloads, parses archives, invokes quantum hardware or claims measurements.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qfabric.dataset_baseline import (
    MAX_CATALOG_BYTES,
    MAX_COUNTS_BYTES,
    audit_local_candidate_file,
    compute_synthetic_count_baseline,
    validate_ai_eval_catalog,
    validate_catalog,
)


def _read(path: Path, limit: int) -> bytes:
    if path.stat().st_size > limit:
        raise ValueError(f"{path.name}: file exceeds size limit")
    raw = path.read_bytes()
    if len(raw) > limit:
        raise ValueError(f"{path.name}: file exceeds size limit")
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    inspect = modes.add_parser("validate-catalog", help="Validate metadata-only candidates")
    inspect.add_argument("catalog", type=Path)
    ai = modes.add_parser("validate-ai-catalog", help="Validate distinct QCalEval candidates")
    ai.add_argument("catalog", type=Path)
    audit = modes.add_parser("audit-local-file", help="Hash local file (no parsing or approval)")
    audit.add_argument("catalog", type=Path)
    audit.add_argument("dataset_id")
    audit.add_argument("file", type=Path)
    audit.add_argument("--output", type=Path)
    baseline = modes.add_parser("synthetic-baseline", help="Compute synthetic error rates and CI")
    baseline.add_argument("counts", type=Path)
    baseline.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.mode == "validate-catalog":
            doc = validate_catalog(_read(args.catalog, MAX_CATALOG_BYTES))
            print(json.dumps({
                "schemaVersion": doc["schemaVersion"],
                "catalogCandidates": len(doc["datasets"]),
                "downloadedDatasets": 0,
                "validatedMeasurements": 0,
                "status": "metadata-only; all raw files unverified",
            }, indent=2))
        elif args.mode == "validate-ai-catalog":
            doc = validate_ai_eval_catalog(_read(args.catalog, MAX_CATALOG_BYTES))
            print(json.dumps({
                "schemaVersion": doc["schemaVersion"],
                "aiEvaluationCandidates": len(doc["datasets"]),
                "modelEvaluationsExecuted": 0,
                "measurementDatasetsAccepted": 0,
            }, indent=2))
        elif args.mode == "audit-local-file":
            result = json.dumps(audit_local_candidate_file(
                _read(args.catalog, MAX_CATALOG_BYTES), args.dataset_id, args.file
            ), indent=2, allow_nan=False) + "\n"
            if args.output:
                args.output.write_text(result, encoding="utf-8")
                print(f"Wrote unapproved local-byte audit: {args.output}")
            else:
                print(result, end="")
        else:
            doc = compute_synthetic_count_baseline(_read(args.counts, MAX_COUNTS_BYTES))
            result = json.dumps(doc, indent=2, allow_nan=False) + "\n"
            if args.output:
                args.output.write_text(result, encoding="utf-8")
                print(f"Wrote synthetic-only baseline: {args.output}")
            else:
                print(result, end="")
    except (ValueError, OSError, TypeError) as exc:
        print(f"Baseline refused: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
