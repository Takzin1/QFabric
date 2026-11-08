"""Re-analyse locally held Caune Figure 4 feedback CSVs; never transmit originals.

Usage:
python scripts/caune_feedback_audit.py \
  fig4b_decoding_response_time.csv \
  figS4c_feedback_response_time_probability_density_data.csv \
  figS4c_feedback_response_time_probability_density_fit_parameters.csv \
  figS4d_t1_time_fitting.csv \
  --output /tmp/caune-feedback.json

The inputs must byte-match the four user-uploaded file SHA-256 pins.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qfabric.caune_feedback import MAX_CSV_BYTES, audit_caune_feedback_figures


def _read(path: Path) -> bytes:
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_CSV_BYTES:
        raise ValueError(f"not a bounded local file: {path}")
    raw = path.read_bytes()
    if not 0 < len(raw) <= MAX_CSV_BYTES:
        raise ValueError("source file changed or is too large")
    return raw


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fig4b", type=Path)
    ap.add_argument("si_kde", type=Path)
    ap.add_argument("si_gamma", type=Path)
    ap.add_argument("si_t1", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        ap.error("refusing to overwrite existing evidence report")
    result = audit_caune_feedback_figures(
        _read(args.fig4b), _read(args.si_kde),
        _read(args.si_gamma), _read(args.si_t1),
    )
    with args.output.open("x", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2, ensure_ascii=False, allow_nan=False)
        fp.write("\n")
    print(f"Created evidence audit {args.output} (no author source files copied)")


if __name__ == "__main__":
    main()
