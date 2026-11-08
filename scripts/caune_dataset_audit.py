"""Audit three local Caune 2024 data files and emit only derived summary JSON.

Original measured-like files and paper PDF remain local. Nothing is fetched or
sent to a QPU. Writing an existing report is refused to preserve provenance.

Usage:
python scripts/caune_dataset_audit.py \
  decoder_timings_each_repetition.csv \
  defect_rates_per_round.txt \
  defect_rates_per_round_stability_9.txt \
  --output caune2024-audit.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qfabric.caune_evidence import (
    MAX_DEFECT_BYTES,
    MAX_TIMING_BYTES,
    audit_uploaded_caune_bundle,
)


def _bounded_bytes(path: Path, limit: int) -> bytes:
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError(f"file missing, empty, or exceeds {limit} bytes: {path.name}")
    raw = path.read_bytes()
    if not 0 < len(raw) <= limit:
        raise ValueError("file changed size while being read")
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timing_csv", type=Path)
    parser.add_argument("defect_25", type=Path)
    parser.add_argument("defect_stability_9", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("report already exists; refusing overwrite")
    result = audit_uploaded_caune_bundle(
        _bounded_bytes(args.timing_csv, MAX_TIMING_BYTES),
        _bounded_bytes(args.defect_25, MAX_DEFECT_BYTES),
        _bounded_bytes(args.defect_stability_9, MAX_DEFECT_BYTES),
    )
    with args.output.open("x", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2, ensure_ascii=False, allow_nan=False)
        fp.write("\n")
    print(f"Created {args.output} using pinned user-provided input bytes (no QPU accessed)")


if __name__ == "__main__":
    main()
