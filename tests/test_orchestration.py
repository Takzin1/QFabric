"""CPU-only research orchestration contracts; no model SDK or hardware calls."""

import json
from pathlib import Path

import pytest

from qfabric.orchestration import (
    ASSESSMENT_VERSION,
    PROPOSAL_VERSION,
    REVIEW_VERSION,
    make_assessment,
    make_review,
    parse_proposal,
    parse_snapshot,
    sha256,
)

SOURCE = (Path(__file__).parent / "fixtures" / "crystaltwin_snapshot.synthetic.json").read_bytes()


def _raw(value):
    return json.dumps(value, ensure_ascii=False).encode()


def _proposal(**overrides):
    doc = {
        "schemaVersion": PROPOSAL_VERSION,
        "kind": "educational_parameter_change",
        "proposalId": "test-001",
        "snapshotSha256": sha256(SOURCE),
        "source": {
            "origin": "unverified_model",
            "providerLabel": "unverified-nebius",
            "modelLabel": "unverified-open-model",
        },
        "hypothesis": "A slower cooling rate may change the educational output.",
        "rationale": "Test the hypothetical change; do not infer process safety.",
        "changes": {"coolingRate": 0.25},
        "requestedAction": "simulation_only",
    }
    doc.update(overrides)
    return doc


def test_offline_model_proposal_requires_manual_review() -> None:
    baseline = parse_snapshot(SOURCE)
    assert baseline["kind"] == "educational_snapshot"
    assessment = make_assessment(SOURCE, _raw(_proposal()))
    assert assessment["schemaVersion"] == ASSESSMENT_VERSION
    assert assessment["status"] == "ready_for_review"
    assert assessment["proposedInput"]["coolingRate"] == 0.25
    assert assessment["proposedInput"]["temperature"] == baseline["input"]["temperature"]
    assert assessment["changes"] == [{
        "parameter": "coolingRate", "from": 0.5, "to": 0.25, "unit": "°C/min"
    }]
    assert assessment["modelInvoked"] is False
    assert assessment["reviewRequired"] is True
    assert assessment["humanApproved"] is False
    assert assessment["hardwareDispatchAllowed"] is False
    assert assessment["physicalMeasurement"] is False


def test_self_attested_approval_is_only_manual_simulation_input() -> None:
    proposal = _raw(_proposal())
    assessment = _raw(make_assessment(SOURCE, proposal))
    result = make_review(
        SOURCE, proposal, assessment, reviewer_label="lab-human",
        decision="approve",
    )
    assert result["schemaVersion"] == REVIEW_VERSION
    assert result["status"] == "approved_for_manual_simulation"
    assert result["simulationInput"]["coolingRate"] == 0.25
    assert result["reviewerAuthenticated"] is False
    assert result["automaticExecution"] is False
    assert result["hardwareDispatchAllowed"] is False
    assert result["assessmentSha256"] == sha256(assessment)


def test_rejection_releases_no_simulation_input() -> None:
    proposal = _raw(_proposal())
    report = _raw(make_assessment(SOURCE, proposal))
    result = make_review(
        SOURCE, proposal, report, reviewer_label="human", decision="reject",
    )
    assert result["simulationInput"] is None
    assert result["status"] == "rejected_by_reviewer"


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"coolingRate": 9.0}, "outside educational model bounds"),
        ({"coolingRate": 0.5}, "unchanged from source input"),
        ({"timeSteps": 15.5}, "must be an integer"),
        ({"temperature": 19}, "outside educational model bounds"),
        ({"concentration": 0.9}, "outside educational model bounds"),
        ({"stirringSpeed": 1001}, "outside educational model bounds"),
    ],
)
def test_unsafe_or_noop_proposal_rejected_as_data(changes, reason) -> None:
    result = make_assessment(SOURCE, _raw(_proposal(changes=changes)))
    assert result["status"] == "rejected"
    assert result["proposedInput"] is None
    assert any(reason in item for item in result["rejectionReasons"])
    with pytest.raises(ValueError, match="cannot approve"):
        make_review(
            SOURCE,
            _raw(_proposal(changes=changes)),
            _raw(result),
            reviewer_label="human",
            decision="approve",
        )


@pytest.mark.parametrize(
    "update",
    [
        {"snapshotSha256": "0" * 64},
        {"requestedAction": "execute_hardware"},
        {"kind": "quantum_device_command"},
        {"schemaVersion": "qfabric-research-proposal/999"},
        {"changes": {"qick.acquire": 1.0}},
        {"changes": {"coolingRate": True}},
        {"changes": {"coolingRate": float("nan")}},
        {"changes": {"coolingRate": float("inf")}},
        {"changes": {"coolingRate": 0.2, "temperature": 50, "impurityLevel": 0.2,
                     "stirringSpeed": 300}},
        {"changes": {}},
        {"source": {"origin": "verified_model", "providerLabel": "unknown",
                    "modelLabel": "none"}},
        {"hypothesis": ""},
        {"rationale": "x" * 601},
        {"unknown": 1},
    ],
)
def test_untrusted_proposal_fails_closed(update) -> None:
    proposal = _proposal(**update)
    with pytest.raises((ValueError, TypeError)):
        make_assessment(SOURCE, _raw(proposal))


@pytest.mark.parametrize(
    "payload",
    [
        b'{"a":1,"a":2}',
        b'{"schemaVersion":"x","schemaVersion":"y"}',
        b'{"x": NaN}',
        b'{"x": Infinity}',
        b"[" * 20000,
        b" " * 20000,
    ],
)
def test_rejects_duplicate_keys_invalid_json_and_oversized_proposals(payload) -> None:
    with pytest.raises((ValueError, TypeError)):
        parse_proposal(payload)


def test_detects_tampered_snapshot_and_explicit_measurement_claim() -> None:
    proposal = _raw(_proposal())
    with pytest.raises(ValueError, match="another snapshot"):
        make_assessment(SOURCE + b" ", proposal)
    source = json.loads(SOURCE)
    source["source"]["provenance"] = "measured"
    with pytest.raises(ValueError, match="synthetic"):
        parse_snapshot(_raw(source))


def test_review_does_not_accept_modified_assessment_even_when_digest_is_valid() -> None:
    proposal = _raw(_proposal())
    assessment = make_assessment(SOURCE, proposal)
    assessment["humanApproved"] = True
    with pytest.raises(ValueError, match="assessment differs"):
        make_review(
            SOURCE, proposal, _raw(assessment),
            reviewer_label="human", decision="approve",
        )


def test_review_rejects_swapped_proposal_and_snapshot() -> None:
    original = _raw(_proposal())
    assessment = _raw(make_assessment(SOURCE, original))
    different = _raw(_proposal(proposalId="changed-but-same-parameter"))
    with pytest.raises(ValueError, match="assessment differs"):
        make_review(
            SOURCE, different, assessment, reviewer_label="human", decision="approve",
        )


def test_multifield_plan_is_sorted_and_no_automatic_dispatch() -> None:
    proposal = _proposal(changes={"stirringSpeed": 400, "coolingRate": 0.2})
    report = make_assessment(SOURCE, _raw(proposal))
    assert report["status"] == "ready_for_review"
    assert [v["parameter"] for v in report["changes"]] == [
        "coolingRate", "stirringSpeed"
    ]
    assert report["hardwareDispatchAllowed"] is False
