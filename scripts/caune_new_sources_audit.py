"""Audit *new* Caune 2024 local sources; do not copy author raw data.

Usage:
python scripts/caune_new_sources_audit.py /local/caune_source_folder \
  --output /tmp/caune-new-evidence.json

Folder must contain:
  mean_decoding_time.txt, lep_mwpm_stability_9.txt, fast_feedback_raw_data.h5

Use Python 3.11+ and pip install -e ".[research-hdf5]".
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qfabric.caune_addenda import (
    MEAN_NAME,
    STABILITY_NAME,
    audit_additional_summaries,
)
from qfabric.caune_hdf5 import HDF5_NAME, audit_fast_feedback_hdf5


def _read_bounded(path: Path) -> bytes:
    if not path.is_file() or not 0 < path.stat().st_size <= 4096:
        raise ValueError(f"missing or oversized Caune text data: {path.name}")
    raw = path.read_bytes()
    if not 0 < len(raw) <= 4096:
        raise ValueError("source file changed during read")
    return raw


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source_dir", type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    if args.output.exists():
        ap.error("refusing to overwrite previously created evidence report")
    result = {
        "schemaVersion": "qfabric-caune-2024-new-sources-offline-audit/1",
        "summaryTables": audit_additional_summaries(
            _read_bounded(args.source_dir / MEAN_NAME),
            _read_bounded(args.source_dir / STABILITY_NAME),
        ),
        "rawHdf5": audit_fast_feedback_hdf5(args.source_dir / HDF5_NAME),
        "sourceFilesIncludedInReport": False,
        "independentHardwareExperimentPerformed": False,
    }
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, ensure_ascii=False, allow_nan=False)
        output.write("\n")
    print(f"Created {args.output}; user-supplied sources were not redistributed")


if __name__ == "__main__":
    main()
