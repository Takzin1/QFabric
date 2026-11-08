"""Audit five local Caune 2024 author LEP tables without accessing hardware.

Usage:
    python scripts/caune_lep_audit.py /path/to/folder-with-five-lep-files \
      --output /tmp/caune-lep-audit.json

Original author tables must remain local. This script emits only a derived
report (no overwrite), with provenance boundaries and no significance tests.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qfabric.caune_lep import MAX_BYTES_PER_FILE, SOURCE_SPECS, audit_caune_lep_bundle


def _read_bounded(path: Path) -> bytes:
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES_PER_FILE:
        raise ValueError("missing, empty or oversized source: " + path.name)
    content = path.read_bytes()
    if not 0 < len(content) <= MAX_BYTES_PER_FILE:
        raise ValueError("source changed during read")
    return content


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite prior evidence report")
    result = audit_caune_lep_bundle({
        filename: _read_bounded(args.source_directory / filename)
        for filename in SOURCE_SPECS
    })
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2, ensure_ascii=False, allow_nan=False)
        output.write("\n")
    print(f"Wrote {args.output} (five verified uploaded-copy hashes; no QPU run)")


if __name__ == "__main__":
    main()
