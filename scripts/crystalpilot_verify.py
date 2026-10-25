"""Verify a CrystalPilot evidence file with QFabric's own gate (offline).

    python scripts/crystalpilot_verify.py crystalpilot-run-....json [--json]

Exit 0 = PASS, 2 = FAIL, 1 = unreadable input. PASS means file integrity plus
QFabric gate/review consistency; it does not authenticate the producer, prove a
live model call or validate any scientific claim.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from qfabric.evidence import MAX_EVIDENCE_BYTES, verify_evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--json", action="store_true", help="print the machine-readable report")
    args = parser.parse_args(argv)
    try:
        if not args.evidence.is_file():
            raise ValueError("evidence must be a regular file")
        if args.evidence.stat().st_size > MAX_EVIDENCE_BYTES:
            raise ValueError("evidence exceeds 1 MiB")
        report = verify_evidence(args.evidence.read_bytes())
    except (OSError, ValueError) as exc:
        print(f"Evidence verification refused: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for check in report["checks"]:
            mark = {"pass": "✓", "fail": "✗", "warn": "!", "skip": "–"}[check["status"]]
            print(f"{mark} {check['id']}: {check['detail']}")
        print(f"{report['overall']} · file integrity {report['integrity']}")
        print(report["notice"])
    if report["integrity"] == "UNREADABLE":
        return 1
    return 0 if report["overall"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
