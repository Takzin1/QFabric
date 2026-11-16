"""Offline, fail-closed research proposal review boundary for CrystalTwinAI.

Untrusted model text is DATA, not instructions. This module never imports an
LLM SDK, connects to a model/quantum device, simulates an experiment, or calls
a hardware executor. An accepted proposal is NOT an approved proposal.

Experiment manifests (second half of this module) follow the same rule: a
manifest can only select an allowlisted, deterministic OFFLINE analysis, and a
manifest of model origin runs only after a human review bound to its bytes.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping
from typing import Any

from qfabric.research import PROVENANCE
from qfabric.research.benchmark import canonical_sha256, run_decoder_benchmark

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


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("JSON number exceeds the finite floating-point range")
    return number


def _same_json(left: Any, right: Any) -> bool:
    """JSON-model equality: Python's ``True == 1 == 1.0`` must not pass as agreement."""
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _same_json(item, right[key]) for key, item in left.items()
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(map(_same_json, left, right))
    return left == right


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
            parse_float=_finite_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
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
    if not _same_json(reported, expected):
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


# --- Versioned experiment manifests: preregistered, reviewable, replayable ---

MANIFEST_VERSION = "qfabric-experiment-manifest/1"
MANIFEST_REVIEW_VERSION = "qfabric-experiment-review/1"
RESULT_VERSION = "qfabric-experiment-result/1"
MAX_MANIFEST_BYTES = 16 * 1024
MAX_RESULT_BYTES = 2 * 1024 * 1024
MANIFEST_FIELDS = frozenset({
    "schemaVersion", "kind", "experimentId", "source", "hypothesis", "rationale",
    "analysis", "inputs", "endpoint", "requestedAction",
})
ORIGINS = ("unverified_model", "human", "synthetic_fixture")


def _benchmark_metric(report: dict[str, Any], endpoint: dict[str, Any]) -> float:
    for row in report["summary"]:
        if row["decoder"] == endpoint["subject"]:
            return row[endpoint["metric"]]
    raise ValueError("endpoint subject is not a decoder in the analysed spec")


# Allowlisted offline analyses: name -> (input roles, runner, metric reader, metrics).
# Adding hardware dispatch here is out of scope by design; see AGENTS.md.
ANALYSES: dict[str, tuple[
    tuple[str, ...],
    Callable[..., dict[str, Any]],
    Callable[[dict[str, Any], dict[str, Any]], float],
    frozenset[str],
]] = {
    "decoder_benchmark": (
        ("spec",), run_decoder_benchmark, _benchmark_metric,
        frozenset({"oracleAgreementFraction", "intervalCoverageFraction"}),
    ),
}


def parse_manifest(raw: bytes) -> dict[str, Any]:
    """Validate an untrusted experiment manifest. Prose fields stay inert data."""
    doc = _decode(raw, limit=MAX_MANIFEST_BYTES, label="manifest")
    _fields(doc, MANIFEST_FIELDS, "manifest")
    if doc["schemaVersion"] != MANIFEST_VERSION or doc["kind"] != "offline_analysis":
        raise ValueError("unsupported experiment manifest schema")
    if doc["requestedAction"] != "offline_analysis_only":
        raise ValueError("only offline_analysis_only is allowed; hardware commands are forbidden")
    _text(doc["experimentId"], "experimentId", 100)
    source = _object(doc["source"], "manifest.source")
    _fields(source, frozenset({"origin", "providerLabel", "modelLabel"}), "manifest.source")
    if source["origin"] not in ORIGINS:
        raise ValueError("manifest origin must be explicitly declared")
    _text(source["providerLabel"], "providerLabel", 80)
    _text(source["modelLabel"], "modelLabel", 120)
    _text(doc["hypothesis"], "hypothesis", 600)
    _text(doc["rationale"], "rationale", 600)
    if not isinstance(doc["analysis"], str) or doc["analysis"] not in ANALYSES:
        raise ValueError("analysis is not on the offline allowlist")
    roles, _, _, metrics = ANALYSES[doc["analysis"]]
    inputs = doc["inputs"]
    if not isinstance(inputs, list) or len(inputs) != len(roles):
        raise ValueError("manifest inputs do not match the analysis input roles")
    for role, item in zip(roles, inputs, strict=True):
        entry = _object(item, "manifest input")
        _fields(entry, frozenset({"role", "sha256", "provenance"}), "manifest input")
        _digest(entry["sha256"], "input sha256")
        if entry["role"] != role or entry["provenance"] not in PROVENANCE:
            raise ValueError("manifest input role or provenance label is not recognised")
    endpoint = _object(doc["endpoint"], "manifest.endpoint")
    _fields(endpoint, frozenset({"metric", "subject", "minimum"}), "manifest.endpoint")
    if not isinstance(endpoint["metric"], str) or endpoint["metric"] not in metrics:
        raise ValueError("endpoint metric is not defined for this analysis")
    _text(endpoint["subject"], "endpoint.subject", 80)
    if not 0 <= _number(endpoint["minimum"], "endpoint.minimum") <= 1:
        raise ValueError("endpoint.minimum must lie within [0, 1]")
    return doc


def make_manifest_review(
    manifest_raw: bytes, *, reviewer_label: str, decision: str,
) -> dict[str, Any]:
    """Self-attested review bound to the manifest bytes. Not a signature."""
    reviewer = _text(reviewer_label, "reviewer_label", 120)
    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be approve or reject")
    manifest = parse_manifest(manifest_raw)
    return {
        "schemaVersion": MANIFEST_REVIEW_VERSION,
        "kind": "self_attested_offline_analysis_review",
        "status": (
            "approved_for_offline_analysis" if decision == "approve" else "rejected_by_reviewer"
        ),
        "reviewerLabel": reviewer,
        "reviewerAuthenticated": False,
        "experimentId": manifest["experimentId"],
        "manifestSha256": sha256(manifest_raw),
        "automaticExecution": False,
        "hardwareDispatchAllowed": False,
        "notice": (
            "Reviewer identity is self-declared, not authenticated. Approval releases "
            "one deterministic offline analysis only; no quantum or process hardware control."
        ),
    }


def _check_review(manifest_raw: bytes, origin: str, review_raw: bytes | None) -> str | None:
    if review_raw is None:
        if origin == "unverified_model":
            raise ValueError("a model-originated manifest requires an approving human review")
        return None
    review = _decode(review_raw, limit=MAX_ASSESSMENT_BYTES, label="review")
    if not _same_json(review, make_manifest_review(
        manifest_raw, reviewer_label=_text(review.get("reviewerLabel"), "reviewerLabel", 120),
        decision="approve",
    )):
        raise ValueError("review is not an approval of exactly this manifest")
    return sha256(review_raw)


def run_experiment(
    manifest_raw: bytes, inputs: Mapping[str, bytes], *, review_raw: bytes | None = None,
) -> dict[str, Any]:
    """Run one preregistered offline analysis and return a structured result.

    Refuses (raises) when the manifest or review is unacceptable. Once those
    pass, a bad input or analysis error is REPORTED as ``status: failed`` so the
    failure itself becomes a reproducible artifact. Deterministic: no clock,
    host or timing information enters the result.
    """
    manifest = parse_manifest(manifest_raw)
    review_hash = _check_review(manifest_raw, manifest["source"]["origin"], review_raw)
    roles, runner, read_metric, _ = ANALYSES[manifest["analysis"]]
    endpoint = manifest["endpoint"]
    report = observed = failure = None
    stage = "input_verification"
    try:
        if set(inputs) != set(roles):
            raise ValueError("supplied inputs do not match the manifest input roles")
        for entry in manifest["inputs"]:
            if sha256(inputs[entry["role"]]) != entry["sha256"]:
                raise ValueError(f"input {entry['role']!r} differs from its preregistered SHA-256")
        stage = "analysis"
        report = runner(*(inputs[role] for role in roles))
        if report.get("dataProvenance") != manifest["inputs"][0]["provenance"]:
            raise ValueError("analysis provenance differs from the manifest's declared provenance")
        observed = read_metric(report, endpoint)
    except (ValueError, TypeError) as exc:
        failure = {"stage": stage, "error": str(exc)}
        report = observed = None
    result = {
        "schemaVersion": RESULT_VERSION,
        "kind": "offline_analysis_result",
        "status": "failed" if failure else "completed",
        "experimentId": manifest["experimentId"],
        "manifestSha256": sha256(manifest_raw),
        "reviewSha256": review_hash,
        "humanReviewed": review_hash is not None,
        "declaredOrigin": manifest["source"],
        "hypothesis": manifest["hypothesis"],
        "analysis": manifest["analysis"],
        "inputs": manifest["inputs"],
        "endpoint": {
            **endpoint,
            "observed": observed,
            "status": (
                "not_evaluated" if failure
                else "met" if observed >= endpoint["minimum"] else "not_met"
            ),
            "preregistered": True,
        },
        "failure": failure,
        "analysisReport": report,
        "automaticExecution": False,
        "hardwareDispatchAllowed": False,
        "physicalMeasurement": False,
        "notice": (
            "Offline analysis of declared inputs only. An endpoint that is met is a "
            "statement about this analysis, not scientific validation of a device."
        ),
    }
    return {**result, "resultDigest": canonical_sha256(result)}


def replay_experiment(
    manifest_raw: bytes, inputs: Mapping[str, bytes], result_raw: bytes, *,
    review_raw: bytes | None = None,
) -> dict[str, Any]:
    """Recompute a stored result from its manifest and inputs and compare exactly."""
    stored = _decode(result_raw, limit=MAX_RESULT_BYTES, label="result")
    recomputed = run_experiment(manifest_raw, inputs, review_raw=review_raw)
    return {
        "identical": _same_json(stored, recomputed),
        "storedDigest": stored.get("resultDigest"),
        "recomputedDigest": recomputed["resultDigest"],
        "recomputedStatus": recomputed["status"],
    }
