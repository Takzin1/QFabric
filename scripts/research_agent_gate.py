"""Offline research proposal workflow. All outputs are local JSON evidence.

`prepare` writes a synthetic fixture (NOT a model output). Real model-generated
proposals must obey the same JSON contract and remain untrusted. `review`
records a self-attestation; it never authenticates a person or drives hardware.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from qfabric.orchestration import (
    MAX_ASSESSMENT_BYTES,
    MAX_PROPOSAL_BYTES,
    MAX_SNAPSHOT_BYTES,
    PARAMETERS,
    PROPOSAL_VERSION,
    make_assessment,
    make_review,
    parse_snapshot,
    sha256,
)


def _read(path: Path, *, limit: int) -> bytes:
    if path.stat().st_size > limit:
        raise ValueError(f"{path.name} exceeds maximum input size")
    raw = path.read_bytes()
    if len(raw) > limit:
        raise ValueError(f"{path.name} exceeds maximum input size")
    return raw


def _write(path: Path, document: dict[str, Any]) -> None:
    payload = json.dumps(
        document, ensure_ascii=False, indent=2, allow_nan=False,
    ) + "\n"
    path.write_text(payload, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Create an explicitly synthetic proposal fixture")
    prepare.add_argument("snapshot", type=Path)
    prepare.add_argument("proposal", type=Path)
    prepare.add_argument("--parameter", choices=tuple(PARAMETERS), required=True)
    prepare.add_argument("--value", type=float, required=True)
    prepare.add_argument("--hypothesis", default="Investigate the educational simulation response")
    prepare.add_argument("--rationale", default="Demonstration fixture, not a model recommendation")
    assess = commands.add_parser("assess", help="Validate and assess untrusted proposal JSON")
    assess.add_argument("snapshot", type=Path)
    assess.add_argument("proposal", type=Path)
    assess.add_argument("assessment", type=Path)
    review = commands.add_parser("review", help="Self-attest review for manual educational use")
    review.add_argument("snapshot", type=Path)
    review.add_argument("proposal", type=Path)
    review.add_argument("assessment", type=Path)
    review.add_argument("review_record", type=Path)
    review.add_argument("--reviewer-label", required=True)
    review.add_argument("--decision", required=True, choices=("approve", "reject"))
    review.add_argument("--attest-educational-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        source = _read(args.snapshot, limit=MAX_SNAPSHOT_BYTES)
        if args.command == "prepare":
            parse_snapshot(source)
            # Fixture is intentionally labelled synthetic, never as NVIDIA/Nebius inference.
            doc = {
                "schemaVersion": PROPOSAL_VERSION,
                "kind": "educational_parameter_change",
                "proposalId": "synthetic-fixture-001",
                "snapshotSha256": sha256(source),
                "source": {
                    "origin": "synthetic_fixture",
                    "providerLabel": "offline",
                    "modelLabel": "none",
                },
                "hypothesis": args.hypothesis,
                "rationale": args.rationale,
                "changes": {args.parameter: args.value},
                "requestedAction": "simulation_only",
            }
            _write(args.proposal, doc)
            print(f"Synthetic fixture prepared: {args.proposal}")
            return 0
        proposal_raw = _read(args.proposal, limit=MAX_PROPOSAL_BYTES)
        if args.command == "assess":
            result = make_assessment(source, proposal_raw)
            _write(args.assessment, result)
            print(f"Assessment {result['status']}: {args.assessment}")
            return 0 if result["status"] == "ready_for_review" else 2
        if args.decision == "approve" and not args.attest_educational_only:
            raise ValueError("approval requires --attest-educational-only")
        report = _read(args.assessment, limit=MAX_ASSESSMENT_BYTES)
        result = make_review(
            source,
            proposal_raw,
            report,
            reviewer_label=args.reviewer_label,
            decision=args.decision,
        )
        _write(args.review_record, result)
        print(f"Self-attested review {result['status']}: {args.review_record}")
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"Experiment orchestration refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
