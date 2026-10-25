"""Independent Python verifier for CrystalPilot evidence (`crystalpilot-evidence/1`).

CrystalPilot (Takzin1/crystaltwinai, /pilot) records an AI-proposed educational
experiment: snapshot → model output → proposal → gate assessment → self-attested
review → simulation → interpretation. This module re-checks such a file *without*
trusting the TypeScript app:

- recomputes the canonical-JSON body digest (RFC 8785-style, ECMAScript number
  formatting) to detect modification after export;
- re-runs the REAL QFabric research gate (`qfabric.orchestration`) on the
  embedded snapshot and proposal bytes, and recomputes the review;
- validates the recorded workflow state transitions.

It does NOT re-run the CrystalTwinAI simulation (a TypeScript engine); that
replay is done by CrystalPilot's own verifier. A passing result is file
integrity plus gate/review consistency — not authenticated provenance, not proof
of a live model call and not scientific validation.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from typing import Any

from qfabric.orchestration import make_assessment, make_review, parse_snapshot

EVIDENCE_VERSION = "crystalpilot-evidence/1"
MAX_EVIDENCE_BYTES = 1024 * 1024

# Mirrors src/lib/pilot/workflow.ts in CrystalTwinAI.
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "CREATED": ("PROPOSED", "FAILED"),
    "PROPOSED": ("VALIDATED", "REJECTED"),
    "VALIDATED": ("AWAITING_REVIEW",),
    "AWAITING_REVIEW": ("APPROVED", "REJECTED"),
    "APPROVED": ("SIMULATED", "FAILED"),
    "SIMULATED": ("VERIFIED", "INCONCLUSIVE", "FAILED"),
    "REJECTED": (),
    "VERIFIED": (),
    "INCONCLUSIVE": (),
    "FAILED": (),
}


# --------------------------------------------------------------- canonical JSON

def _js_number(value: float) -> str:
    """ECMAScript Number::toString for finite doubles."""
    if isinstance(value, bool):
        raise TypeError("booleans are not numbers")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("canonical JSON requires finite numbers")
    if number == 0:
        return "0"
    if number.is_integer() and abs(number) < 1e21:
        return str(int(number))
    sign = "-" if number < 0 else ""
    # repr() yields the shortest round-tripping digits, as ECMAScript requires.
    text = repr(abs(number))
    mantissa, _, exp_text = text.partition("e")
    whole, _, frac = mantissa.partition(".")
    digits = (whole + frac).lstrip("0")
    exponent10 = int(exp_text) if exp_text else 0
    if whole == "0":
        # 0.000123 → digits "123", value = 0.123 × 10^-3, so n = -(leading zeros).
        point = -(len(frac) - len(frac.lstrip("0"))) + exponent10
    else:
        point = len(whole) + exponent10
    digits = digits.rstrip("0") or "0"
    k, n = len(digits), point
    if k <= n <= 21:
        out = digits + "0" * (n - k)
    elif 0 < n <= 21:
        out = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        out = "0." + "0" * (-n) + digits
    else:
        exponent = n - 1
        sign_e = "+" if exponent >= 0 else "-"
        head = digits[0] + ("." + digits[1:] if k > 1 else "")
        out = f"{head}e{sign_e}{abs(exponent)}"
    return sign + out


def _utf16_key(key: str) -> list[int]:
    data = key.encode("utf-16-be", "surrogatepass")
    return [int.from_bytes(data[i:i + 2], "big") for i in range(0, len(data), 2)]


def canonical_json(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return json.dumps(value)
    if isinstance(value, (int, float)):
        return _js_number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(canonical_json(item) for item in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value, key=_utf16_key)
        return "{" + ",".join(
            json.dumps(k, ensure_ascii=False) + ":" + canonical_json(value[k]) for k in keys
        ) + "}"
    raise TypeError(f"canonical JSON cannot encode {type(value).__name__}")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


# --------------------------------------------------------------- verification

def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, item in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key: {key}")
        out[key] = item
    return out


def _reject_constant(name: str) -> None:
    raise ValueError(f"non-finite JSON constant: {name}")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_history(history: Any) -> str | None:
    if not isinstance(history, list) or not history:
        return "history must be a nonempty array"
    previous: str | None = None
    for entry in history:
        if not isinstance(entry, dict):
            return "history entry must be an object"
        state = entry.get("state")
        if state not in TRANSITIONS:
            return f"unknown workflow state: {state}"
        try:
            datetime.fromisoformat(str(entry.get("at")))
        except ValueError:
            return "history timestamp is invalid"
        if previous is None:
            if state != "CREATED":
                return "history must start at CREATED"
        elif state not in TRANSITIONS[previous]:
            return f"invalid recorded transition {previous} → {state}"
        previous = state
    return None


def verify_evidence(raw: bytes) -> dict[str, Any]:
    checks: list[dict[str, str]] = []

    def add(check_id: str, status: str, detail: str) -> None:
        checks.append({"id": check_id, "status": status, "detail": detail})

    def result(integrity: str) -> dict[str, Any]:
        return {
            "overall": "FAIL" if any(c["status"] == "fail" for c in checks) else "PASS",
            "integrity": integrity,
            "checks": checks,
            "verifier": "qfabric.evidence (Python)",
            "notice": (
                "File integrity and QFabric gate/review recomputation only. The "
                "CrystalTwinAI simulation was not re-run here; no producer "
                "authentication; no scientific validation."
            ),
        }

    if len(raw) > MAX_EVIDENCE_BYTES:
        add("size", "fail", "evidence exceeds 1 MiB")
        return result("UNREADABLE")
    try:
        doc = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        add("parse", "fail", str(exc) or "evidence must be UTF-8 JSON")
        return result("UNREADABLE")
    if not isinstance(doc, dict) or doc.get("schemaVersion") != EVIDENCE_VERSION or not isinstance(
        doc.get("body"), dict
    ) or not isinstance(doc.get("integrity"), dict) or not isinstance(doc["body"].get("run"), dict):
        add("schema", "fail", "not a crystalpilot-evidence/1 document")
        return result("UNREADABLE")
    add("schema", "pass", "recognised crystalpilot-evidence/1 document")

    integrity = "MISMATCH"
    try:
        digest = canonical_sha256(doc["body"])
        if digest == doc["integrity"].get("bodySha256"):
            integrity = "VERIFIED"
            add("integrity", "pass", f"canonical body SHA-256 matches ({digest[:16]}…)")
        else:
            add("integrity", "fail", "body SHA-256 mismatch: the file was modified after export")
    except (TypeError, ValueError) as exc:
        add("integrity", "fail", f"body cannot be canonicalised: {exc}")

    run = doc["body"]["run"]

    def guarded(check_id: str, fn) -> None:
        try:
            fn()
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            add(check_id, "fail", str(exc) or type(exc).__name__)

    def snapshot() -> None:
        text = run["snapshotText"]
        if _sha(text) != run["snapshotSha256"]:
            raise ValueError("snapshot SHA-256 does not match the embedded snapshot bytes")
        parse_snapshot(text.encode("utf-8"))
        add("snapshot_hash", "pass", "snapshot matches its SHA-256 and the QFabric snapshot contract")

    def history() -> None:
        problem = check_history(run["history"])
        if problem:
            raise ValueError(problem)
        states = [h["state"] for h in run["history"]]
        approved = run.get("reviewText") is not None and json.loads(run["reviewText"]).get(
            "status") == "approved_for_manual_simulation"
        if ("APPROVED" in states) != approved:
            raise ValueError("APPROVED state and approval record disagree")
        if ("SIMULATED" in states) != (run.get("experiment") is not None):
            raise ValueError("SIMULATED state and experiment outcome disagree")
        add("history", "pass", f"valid transitions ending in {states[-1]}")

    def inference() -> None:
        inf = run.get("inference")
        if inf is None:
            if not run.get("inferenceError"):
                raise ValueError("missing inference record")
            add("inference_record", "pass", f"no inference: {run['inferenceError'].get('kind')}")
            return
        if _sha(inf["rawContent"]) != inf["rawContentSha256"]:
            raise ValueError("recorded model content does not match its SHA-256")
        if inf["mode"] == "live_nebius":
            if inf["provider"] != "nebius-token-factory" or inf["fixtureId"] is not None:
                raise ValueError("live inference record is internally inconsistent")
            add("inference_record", "warn",
                "self-reported LIVE call; provenance is not authenticated by this verifier")
        elif inf["mode"] == "offline_fixture":
            if inf["provider"] != "offline" or not inf["fixtureId"]:
                raise ValueError("offline record must name its fixture")
            add("inference_record", "pass", f"OFFLINE fixture {inf['fixtureId']}; no model was called")
        else:
            raise ValueError(f"unknown inference mode: {inf['mode']}")

    def gate() -> None:
        proposal = run["proposalText"]
        if _sha(proposal) != run["proposalSha256"]:
            raise ValueError("proposal SHA-256 mismatch")
        try:
            expected = make_assessment(
                run["snapshotText"].encode("utf-8"), proposal.encode("utf-8"))
        except ValueError as exc:
            if run.get("assessmentText") is None and run["history"][-1]["state"] == "REJECTED":
                add("gate_recompute", "pass", f"QFabric gate refusal reproduced: {exc}")
                return
            raise
        if run.get("assessmentText") is None or json.loads(run["assessmentText"]) != expected:
            raise ValueError("recorded assessment differs from the QFabric gate result")
        add("gate_recompute", "pass", f"QFabric gate reproduced: {expected['status']}")

    def review() -> None:
        claimed = json.loads(run["reviewText"])
        decision = "approve" if claimed.get("status") == "approved_for_manual_simulation" else "reject"
        expected = make_review(
            run["snapshotText"].encode("utf-8"),
            run["proposalText"].encode("utf-8"),
            run["assessmentText"].encode("utf-8"),
            reviewer_label=claimed.get("reviewerLabel", ""),
            decision=decision,
        )
        if expected != claimed:
            raise ValueError("review record differs from QFabric recomputation")
        add("review_recompute", "pass",
            f"self-attested {decision} by '{expected['reviewerLabel']}' recomputes (not authenticated)")

    guarded("snapshot_hash", snapshot)
    guarded("history", history)
    guarded("inference_record", inference)
    if run.get("proposalText") is not None:
        guarded("gate_recompute", gate)
    if run.get("reviewText") is not None:
        guarded("review_recompute", review)
    if run.get("experiment") is not None:
        add("simulation_replay", "skip",
            "not performed in Python; run CrystalPilot's verifier (npm run verify:evidence)")
    return result(integrity)
