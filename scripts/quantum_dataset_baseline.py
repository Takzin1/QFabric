"""Offline checks for a research-data catalog and a synthetic count baseline.

Never downloads, parses archives, invokes quantum hardware or claims measurements.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
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
    """Read a bounded regular input file, never blocking on a FIFO/device node."""
    if path.is_symlink():
        raise ValueError("input must not be a symbolic link")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("input must be a regular file")
        if before.st_size > limit:
            raise ValueError(f"{path.name}: file exceeds size limit")
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        if len(raw) > limit:
            raise ValueError(f"{path.name}: file exceeds size limit")
        if (
            len(raw) != before.st_size
            or (
                before.st_size, before.st_mtime_ns, before.st_ino, before.st_dev
            ) != (
                after.st_size, after.st_mtime_ns, after.st_ino, after.st_dev
            )
        ):
            raise ValueError("input changed while reading")
        return raw


def _write_new_report(output: Path, result: str, *source_paths: Path) -> None:
    """Do not truncate source data, input catalogs, or earlier audit evidence."""
    target = output.resolve(strict=False)
    if any(target == source.resolve(strict=False) for source in source_paths):
        raise ValueError("output path would overwrite an input file")
    # Exclusive create also refuses pre-existing files and symlink destinations.
    with output.open("x", encoding="utf-8") as handle:
        handle.write(result)


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
                _write_new_report(args.output, result, args.catalog, args.file)
                print(f"Wrote unapproved local-byte audit: {args.output}")
            else:
                print(result, end="")
        else:
            doc = compute_synthetic_count_baseline(_read(args.counts, MAX_COUNTS_BYTES))
            result = json.dumps(doc, indent=2, allow_nan=False) + "\n"
            if args.output:
                _write_new_report(args.output, result, args.counts)
                print(f"Wrote synthetic-only baseline: {args.output}")
            else:
                print(result, end="")
    except (ValueError, OSError, TypeError) as exc:
        print(f"Baseline refused: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
