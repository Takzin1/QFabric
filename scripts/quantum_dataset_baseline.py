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
    compute_synthetic_count_baseline,
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
