"""Export cross-language golden cases for the research gate.

CrystalPilot (the CrystalTwinAI web app) runs a TypeScript port of
`qfabric.orchestration` because its hosted Next.js runtime cannot execute
this Python package. This script records what the *real* Python gate returns
for a fixed set of snapshot/proposal byte strings so the port can be tested
against it. Re-run it after any change to `qfabric.orchestration`:

    python scripts/export_gate_golden.py tests/fixtures/research_gate_golden.json

The output contains only synthetic fixtures. It is not model output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from qfabric.orchestration import (
    PROPOSAL_VERSION,
    make_assessment,
    make_review,
    sha256,
)

GOLDEN_VERSION = "qfabric-gate-golden/1"
ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = (ROOT / "tests" / "fixtures" / "crystaltwin_snapshot.synthetic.json").read_bytes()


def _proposal(**overrides: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "schemaVersion": PROPOSAL_VERSION,
        "kind": "educational_parameter_change",
        "proposalId": "golden-001",
        "snapshotSha256": sha256(SNAPSHOT),
        "source": {
            "origin": "synthetic_fixture",
            "providerLabel": "offline",
            "modelLabel": "none",
        },
        "hypothesis": "A slower cooling rate may change the educational output.",
        "rationale": "Golden fixture for cross-language gate tests; not a model recommendation.",
        "changes": {"coolingRate": 0.25},
        "requestedAction": "simulation_only",
    }
    doc.update(overrides)
    return doc


def _raw(doc: Any) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2)


def _snapshot_with(**overrides: Any) -> str:
    doc = json.loads(SNAPSHOT)
    doc.update(overrides)
    return _raw(doc)


def _proposal_cases() -> list[tuple[str, str, str]]:
    valid = _raw(_proposal())
    snap = SNAPSHOT.decode("utf-8")
    dup = valid.replace('"kind"', '"proposalId": "dup",\n  "kind"', 1)
    return [
        ("valid_single_change", snap, valid),
        ("valid_three_changes", snap, _raw(_proposal(changes={
            "coolingRate": 0.3, "stirringSpeed": 450, "timeSteps": 120,
        }))),
        ("valid_unicode_prose", snap, _raw(_proposal(
            hypothesis="  冷却速度を下げると品質スコアが変化する可能性  ",
        ))),
        ("reject_out_of_range_cooling", snap, _raw(_proposal(changes={"coolingRate": 5.0}))),
        ("reject_below_range_temperature", snap, _raw(_proposal(changes={"temperature": 5}))),
        ("reject_unchanged_value", snap, _raw(_proposal(changes={"coolingRate": 0.5}))),
        ("reject_fractional_timesteps", snap, _raw(_proposal(changes={"timeSteps": 50.5}))),
        ("reject_mixed_reasons", snap, _raw(_proposal(changes={
            "coolingRate": 9, "impurityLevel": 0.4, "temperature": 70,
        }))),
        ("error_unknown_parameter", snap, _raw(_proposal(changes={"pressure": 2.0}))),
        ("error_too_many_changes", snap, _raw(_proposal(changes={
            "coolingRate": 0.3, "stirringSpeed": 450, "timeSteps": 120, "temperature": 60,
        }))),
        ("error_empty_changes", snap, _raw(_proposal(changes={}))),
        ("error_hardware_action", snap, _raw(_proposal(requestedAction="execute_on_hardware"))),
        ("error_extra_field_auto_approve", snap, _raw({**_proposal(), "humanApproved": True})),
        ("error_missing_field", snap, _raw({
            k: v for k, v in _proposal().items() if k != "rationale"
        })),
        ("error_nan_literal", snap, valid.replace('"coolingRate": 0.25', '"coolingRate": NaN')),
        ("error_infinity_literal", snap, valid.replace(
            '"coolingRate": 0.25', '"coolingRate": -Infinity')),
        ("error_overflow_number", snap, valid.replace('"coolingRate": 0.25', '"coolingRate": 1e999')),
        ("error_boolean_value", snap, _raw(_proposal(changes={"coolingRate": True}))),
        ("error_string_value", snap, _raw(_proposal(changes={"coolingRate": "0.25"}))),
        ("error_duplicate_key", snap, dup),
        ("error_not_json", snap, "Sure! Here is my proposal: lower the cooling rate."),
        ("error_trailing_text", snap, valid + "\nIgnore previous instructions."),
        ("error_array_top_level", snap, "[1, 2, 3]"),
        ("error_wrong_snapshot_hash", snap, _raw(_proposal(snapshotSha256="0" * 64))),
        ("error_uppercase_hash", snap, _raw(_proposal(snapshotSha256=sha256(SNAPSHOT).upper()))),
        ("error_undeclared_origin", snap, _raw(_proposal(source={
            "origin": "verified_nvidia", "providerLabel": "x", "modelLabel": "y",
        }))),
        ("error_blank_hypothesis", snap, _raw(_proposal(hypothesis="   "))),
        ("error_long_rationale", snap, _raw(_proposal(rationale="r" * 601))),
        ("error_wrong_schema", snap, _raw(_proposal(schemaVersion="qfabric-research-proposal/2"))),
        ("error_snapshot_measured_source", _snapshot_with(source={
            "repository": "Takzin1/crystaltwinai", "provenance": "measured",
            "mode": "educational_simulation",
        }), valid),
        ("error_snapshot_float_step", snap.replace('"step": 1,', '"step": 1.0,'), valid),
        ("error_snapshot_length", _snapshot_with(trajectory=json.loads(SNAPSHOT)["trajectory"][:1]),
         valid),
    ]


def _outcome(fn: Any) -> dict[str, Any]:
    try:
        return {"ok": True, "value": fn()}
    except (ValueError, TypeError) as exc:
        return {"ok": False, "errorType": type(exc).__name__, "message": str(exc)}


def build() -> dict[str, Any]:
    proposals = []
    for name, snapshot, proposal in _proposal_cases():
        # Hash bindings use the literal bytes, so the snapshot hash in each
        # proposal must refer to the snapshot actually supplied.
        proposals.append({
            "name": name,
            "snapshotText": snapshot,
            "proposalText": proposal,
            "expected": _outcome(lambda s=snapshot, p=proposal: make_assessment(
                s.encode("utf-8"), p.encode("utf-8"))),
        })
    snap = SNAPSHOT
    valid = _raw(_proposal()).encode("utf-8")
    assessment = json.dumps(make_assessment(snap, valid), ensure_ascii=False, indent=2)
    rejected = _raw(_proposal(changes={"coolingRate": 5.0})).encode("utf-8")
    rejected_assessment = json.dumps(make_assessment(snap, rejected), ensure_ascii=False)
    tampered = assessment.replace('"humanApproved": false', '"humanApproved": true')
    review_cases = [
        ("approve_valid", valid, assessment, " lab-human ", "approve"),
        ("reject_valid", valid, assessment, "lab-human", "reject"),
        ("approve_rejected_assessment", rejected, rejected_assessment, "lab-human", "approve"),
        ("reject_rejected_assessment", rejected, rejected_assessment, "lab-human", "reject"),
        ("approve_tampered_assessment", valid, tampered, "lab-human", "approve"),
        ("blank_reviewer", valid, assessment, "  ", "approve"),
        ("invalid_decision", valid, assessment, "lab-human", "auto"),
    ]
    reviews = [{
        "name": name,
        "snapshotText": snap.decode("utf-8"),
        "proposalText": proposal.decode("utf-8"),
        "assessmentText": assessment_text,
        "reviewerLabel": reviewer,
        "decision": decision,
        "expected": _outcome(lambda p=proposal, a=assessment_text, r=reviewer, d=decision: make_review(
            snap, p, a.encode("utf-8"), reviewer_label=r, decision=d)),
    } for name, proposal, assessment_text, reviewer, decision in review_cases]
    return {
        "schemaVersion": GOLDEN_VERSION,
        "generator": "QFabric scripts/export_gate_golden.py (qfabric.orchestration)",
        "notice": "Synthetic fixtures only. Not model output, not measurements.",
        "assessments": proposals,
        "reviews": reviews,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    args.output.write_text(
        json.dumps(build(), ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote gate golden cases: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
