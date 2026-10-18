"""Offline, fail-closed research proposal review boundary for CrystalTwinAI.

Untrusted model text is DATA, not instructions. This module never imports an
LLM SDK, connects to a model/quantum device, simulates an experiment, or calls
a hardware executor. An accepted proposal is NOT an approved proposal.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

SNAPSHOT_VERSION = "crystaltwin-qfabric-snapshot/1"
PROPOSAL_VERSION = "qfabric-research-proposal/1"
ASSESSMENT_VERSION = "qfabric-research-assessment/1"
REVIEW_VERSION = "qfabric-human-review/1"
MAX_SNAPSHOT_BYTES = 512 * 1024
MAX_PROPOSAL_BYTES = 16 * 1024
MAX_ASSESSMENT_BYTES = 32 * 1024
MAX_CHANGES = 3

# Pinned to CrystalTwinAI's src/config/parameters.ts (2026-10-18).
# These are educational UI/model input limits, NOT physical safety limits.
PARAMETERS: dict[str, tuple[float, float, str]] = {
    "temperature": (20.0, 90.0, "°C"),
    "concentration": (0.1, 0.6, "g/mL"),
    "stirringSpeed": (0.0, 1000.0, "rpm"),
    "coolingRate": (0.05, 2.0, "°C/min"),
    "impurityLevel": (0.0, 5.0, "%"),
    "timeSteps": (10.0, 200.0, "steps"),
}
SNAPSHOT_FIELDS = frozenset({
    "schemaVersion", "kind", "source", "input", "summary", "trajectory",
})
SUMMARY_FIELDS = frozenset({
    "avgGrowthRate", "stabilityScore", "qualityScore", "finalYield",
    "maxSupersaturation", "nucleationEvents",
})
ROW_FIELDS = frozenset({
    "step", "temperature", "concentration", "growthRate", "crystalYield",
})
PROPOSAL_FIELDS = frozenset({
    "schemaVersion", "kind", "proposalId", "snapshotSha256",
    "source", "hypothesis", "rationale", "changes", "requestedAction",
})


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _invalid_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _decode(raw: bytes, *, limit: int, label: str) -> dict[str, Any]:
    if not isinstance(raw, bytes):
        raise TypeError(f"{label} must be UTF-8 bytes")
    if len(raw) > limit:
        raise ValueError(f"{label} exceeds its maximum size")
    try:
        doc = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_pairs,
            parse_constant=_invalid_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    return _object(doc, label)


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return value


def _fields(data: dict[str, Any], expected: frozenset[str], label: str) -> None:
    if set(data) != expected:
        raise ValueError(f"{label} fields differ from the versioned contract")


def _text(value: Any, label: str, max_size: int) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= max_size:
        raise ValueError(f"{label} must be nonempty text of at most {max_size} characters")
    return value.strip()


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be numeric")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{label} must be finite") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        char not in "0123456789abcdef" for char in value
    ):
        raise ValueError(f"{label} must be a lowercase hex SHA-256 digest")
    return value


def parse_snapshot(raw: bytes) -> dict[str, Any]:
    """Only synthetic educational snapshots are eligible for orchestration."""
    doc = _decode(raw, limit=MAX_SNAPSHOT_BYTES, label="snapshot")
    _fields(doc, SNAPSHOT_FIELDS, "snapshot")
    if doc["schemaVersion"] != SNAPSHOT_VERSION or doc["kind"] != "educational_snapshot":
        raise ValueError("unsupported CrystalTwinAI snapshot schema")
    if doc["source"] != {
        "repository": "Takzin1/crystaltwinai",
        "provenance": "synthetic",
        "mode": "educational_simulation",
    }:
        raise ValueError("research gate accepts synthetic educational source only")
    inputs = _object(doc["input"], "snapshot.input")
    if set(inputs) != set(PARAMETERS):
        raise ValueError("snapshot input fields mismatch")
    for name, value in inputs.items():
        _number(value, f"input.{name}")
    steps = _number(inputs["timeSteps"], "input.timeSteps")
    if not steps.is_integer() or not 1 <= steps <= 200:
        raise ValueError("snapshot timeSteps outside 1..200")
    summary = _object(doc["summary"], "snapshot.summary")
    _fields(summary, SUMMARY_FIELDS, "snapshot.summary")
    for key, value in summary.items():
        _number(value, f"summary.{key}")
    rows = doc["trajectory"]
    if not isinstance(rows, list) or len(rows) != steps:
        raise ValueError("snapshot trajectory length differs from timeSteps")
    previous = 0
    for row in rows:
        record = _object(row, "trajectory row")
        _fields(record, ROW_FIELDS, "trajectory row")
        step = record["step"]
        if isinstance(step, bool) or not isinstance(step, int) or not previous < step <= 200:
            raise ValueError("trajectory steps must strictly increase")
        previous = step
        for name in ROW_FIELDS - {"step"}:
            _number(record[name], f"trajectory.{name}")
    return doc


def parse_proposal(raw: bytes) -> dict[str, Any]:
    """Validate an LLM-neutral structured proposal, treating all prose as inert."""
    data = _decode(raw, limit=MAX_PROPOSAL_BYTES, label="proposal")
    _fields(data, PROPOSAL_FIELDS, "proposal")
    if data["schemaVersion"] != PROPOSAL_VERSION or (
        data["kind"] != "educational_parameter_change"
    ):
        raise ValueError("unsupported research proposal schema")
    _text(data["proposalId"], "proposalId", 100)
    _digest(data["snapshotSha256"], "snapshotSha256")
    if data["requestedAction"] != "simulation_only":
        raise ValueError("only simulation_only is allowed; hardware commands are forbidden")
    source = _object(data["source"], "proposal.source")
    _fields(source, frozenset({"origin", "providerLabel", "modelLabel"}), "proposal.source")
    if source["origin"] not in {"unverified_model", "human", "synthetic_fixture"}:
        raise ValueError("model provenance must be explicitly declared as unverified")
    _text(source["providerLabel"], "providerLabel", 80)
    _text(source["modelLabel"], "modelLabel", 120)
    _text(data["hypothesis"], "hypothesis", 600)
    _text(data["rationale"], "rationale", 600)
    changes = _object(data["changes"], "proposal.changes")
    if not 1 <= len(changes) <= MAX_CHANGES:
        raise ValueError("proposal must modify 1..3 parameters")
    for name, value in changes.items():
        if name not in PARAMETERS:
            raise ValueError(f"unsupported simulation parameter: {name}")
        _number(value, f"changes.{name}")
    return data


def make_assessment(snapshot_raw: bytes, proposal_raw: bytes) -> dict[str, Any]:
    """A bounded proposal check. Ready-for-review NEVER implies approval."""
    snapshot = parse_snapshot(snapshot_raw)
    proposal = parse_proposal(proposal_raw)
    if proposal["snapshotSha256"] != sha256(snapshot_raw):
        raise ValueError("proposal references another snapshot SHA-256")
    original = snapshot["input"]
    requested = proposal["changes"]
    reasons: list[str] = []
    deltas: list[dict[str, Any]] = []
    for name in sorted(requested):
        value = _number(requested[name], f"changes.{name}")
        minimum, maximum, unit = PARAMETERS[name]
        if not minimum <= value <= maximum:
            reasons.append(f"{name}: outside educational model bounds [{minimum}, {maximum}]")
        elif name == "timeSteps" and not value.is_integer():
            reasons.append("timeSteps: must be an integer")
        elif value == _number(original[name], f"input.{name}"):
            reasons.append(f"{name}: unchanged from source input")
        else:
            deltas.append({
                "parameter": name,
                "from": original[name],
                "to": requested[name],
                "unit": unit,
            })
    accepted = not reasons
    proposal_hash = sha256(proposal_raw)
    snapshot_hash = sha256(snapshot_raw)
    return {
        "schemaVersion": ASSESSMENT_VERSION,
        "kind": "educational_research_assessment",
        "status": "ready_for_review" if accepted else "rejected",
        "proposalId": proposal["proposalId"],
        "snapshotSha256": snapshot_hash,
        "proposalSha256": proposal_hash,
        "declaredOrigin": proposal["source"],
        "hypothesis": proposal["hypothesis"],
        "rationale": proposal["rationale"],
        "changes": deltas if accepted else [],
        "proposedInput": {**original, **requested} if accepted else None,
        "rejectionReasons": reasons,
        "reviewRequired": True,
        "humanApproved": False,
        "modelInvoked": False,
        "hardwareDispatchAllowed": False,
        "physicalMeasurement": False,
        "scope": "educational_simulation_only",
        "notice": (
            "Model/source labels are unverified. No model, quantum device or physical "
            "equipment was called. This is not scientific process validation."
        ),
    }


def make_review(
    snapshot_raw: bytes,
    proposal_raw: bytes,
    assessment_raw: bytes,
    *,
    reviewer_label: str,
    decision: str,
) -> dict[str, Any]:
    """Create a *self-attested* human decision, not a digital signature.

    The result only releases educational simulation inputs for manual use.
    It provides NO permission or interface to execute hardware.
    """
    reviewer = _text(reviewer_label, "reviewer_label", 120)
    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be approve or reject")
    expected = make_assessment(snapshot_raw, proposal_raw)
    reported = _decode(assessment_raw, limit=MAX_ASSESSMENT_BYTES, label="assessment")
    if reported != expected:
        raise ValueError("assessment differs from recomputed source/proposal evidence")
    if decision == "approve" and expected["status"] != "ready_for_review":
        raise ValueError("cannot approve a rejected assessment")
    return {
        "schemaVersion": REVIEW_VERSION,
        "kind": "self_attested_educational_review",
        "status": (
            "approved_for_manual_simulation" if decision == "approve" else "rejected_by_reviewer"
        ),
        "reviewerLabel": reviewer,
        "reviewerAuthenticated": False,
        "snapshotSha256": expected["snapshotSha256"],
        "proposalSha256": expected["proposalSha256"],
        "assessmentSha256": sha256(assessment_raw),
        "simulationInput": expected["proposedInput"] if decision == "approve" else None,
        "automaticExecution": False,
        "hardwareDispatchAllowed": False,
        "notice": (
            "Reviewer identity is self-declared, not authenticated; manual transfer to "
            "the educational simulator only. No quantum or process hardware control."
        ),
    }
