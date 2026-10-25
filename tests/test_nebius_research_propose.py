"""Network-free contract tests: no API key, billable inference or hardware needed."""

import importlib.util
import json
from pathlib import Path

import pytest

from qfabric.orchestration import make_assessment, sha256

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "nebius_research_propose.py"
SPEC = importlib.util.spec_from_file_location("nebius_research_propose", SCRIPT)
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)
SNAPSHOT = (Path(__file__).parent / "fixtures" / "crystaltwin_snapshot.synthetic.json").read_bytes()


def _response(**updates):
    proposed = {
        "hypothesis": "Try a slower cooling rate in the educational twin.",
        "rationale": "Check educational parameter sensitivity, not physical safety.",
        "changes": {"coolingRate": 0.25},
    }
    proposed.update(updates)
    return _wrap(json.dumps(proposed))


def _wrap(content, *, finish_reason="stop", tool_calls=None):
    message = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return json.dumps({
        "choices": [{"finish_reason": finish_reason, "message": message}],
    }).encode()


def test_model_proposal_is_bound_to_snapshot_and_requires_human_review():
    seen = []

    def fake_transport(payload):
        seen.append(payload)
        return _response()

    proposal, assessment, receipt = adapter.build_proposal(
        SNAPSHOT, transport=fake_transport,
    )
    assert seen[0]["model"] == adapter.DEFAULT_MODEL
    assert seen[0]["stream"] is False
    assert set(proposal) == {
        "schemaVersion", "kind", "proposalId", "snapshotSha256", "source",
        "hypothesis", "rationale", "changes", "requestedAction",
    }
    assert proposal["source"]["origin"] == "unverified_model"
    assert proposal["snapshotSha256"] == sha256(SNAPSHOT)
    assert proposal["requestedAction"] == "simulation_only"
    assert assessment["status"] == "ready_for_review"
    assert assessment["humanApproved"] is False
    assert assessment["reviewRequired"] is True
    assert assessment["hardwareDispatchAllowed"] is False
    assert receipt["providerIdentityAuthenticated"] is False
    assert receipt["simulatorExecuted"] is False
    assert receipt["proposalSha256"] == assessment["proposalSha256"]
    raw_file = (json.dumps(proposal, indent=2, ensure_ascii=False, allow_nan=False)
                + "\n").encode()
    assert receipt["proposalSha256"] == sha256(raw_file)
    assert make_assessment(SNAPSHOT, raw_file) == assessment


def test_out_of_bounds_is_rejected_not_auto_approved():
    proposal, assessment, _ = adapter.build_proposal(
        SNAPSHOT, transport=lambda _: _response(changes={"coolingRate": 800}),
    )
    assert proposal["changes"] == {"coolingRate": 800}
    assert assessment["status"] == "rejected"
    assert assessment["proposedInput"] is None


@pytest.mark.parametrize("response", [
    _wrap('{"hypothesis":"a","rationale":"b","changes":{"coolingRate":0.25},"requestedAction":"execute"}'),
    _wrap('{"hypothesis":"a","rationale":"b","changes":{"coolingRate":0.25,"coolingRate":0.1}}'),
    _wrap('{"hypothesis":"a","rationale":"b","changes":{"coolingRate":NaN}}'),
    _wrap("```json\n{}\n```"),
    _wrap("{}", finish_reason="length"),
    _wrap("{}", tool_calls=[{"function": {"name": "execute"}}]),
    _wrap("[1,2]"),
    _wrap("x" * (adapter.MAX_MODEL_TEXT + 1)),
    json.dumps({"choices": []}).encode(),
    json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": []}}]}).encode(),
    b'{"choices":[],"choices":[]}',
    b"{not json",
    b"0" * (adapter.MAX_REPLY_BYTES + 1),
])
def test_untrusted_response_fails_closed(response):
    with pytest.raises((ValueError, TypeError)):
        adapter.build_proposal(SNAPSHOT, transport=lambda _: response)


@pytest.mark.parametrize("changes", [
    {"qick.acquire": 1}, {"temperature": True},
    {"coolingRate": 0.25, "temperature": 50, "timeSteps": 100,
     "concentration": 0.4},
])
def test_nonconforming_parameters_are_refused(changes):
    with pytest.raises((TypeError, ValueError)):
        adapter.build_proposal(SNAPSHOT, transport=lambda _: _response(changes=changes))


def test_fractional_timestep_is_assessed_and_rejected():
    _, assessment, _ = adapter.build_proposal(
        SNAPSHOT, transport=lambda _: _response(changes={"timeSteps": 13.5}),
    )
    assert assessment["status"] == "rejected"
    assert assessment["proposedInput"] is None


def test_provider_credentials_required_and_not_leaked(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    with pytest.raises(ValueError, match="set NEBIUS_API_KEY"):
        adapter._http_transport({"model": adapter.DEFAULT_MODEL})


def test_cli_refuses_to_overwrite_input_or_existing_evidence(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_bytes(SNAPSHOT)
    receipt = tmp_path / "receipt.json"
    assert adapter.main([str(snapshot), str(snapshot), str(receipt)]) == 1
    proposal = tmp_path / "proposal.json"
    proposal.write_text("original", encoding="utf-8")
    assert adapter.main([str(snapshot), str(proposal), str(receipt)]) == 1
    assert proposal.read_text(encoding="utf-8") == "original"


def test_rejects_untrusted_snapshot_before_network():
    document = json.loads(SNAPSHOT)
    document["source"]["provenance"] = "measured"
    called = []
    with pytest.raises(ValueError):
        adapter.build_proposal(json.dumps(document).encode(),
                               transport=lambda _: called.append(True))
    assert not called


def test_rejects_malformed_model_id_before_network():
    with pytest.raises(ValueError, match="model identifier"):
        adapter.build_proposal(SNAPSHOT, model="evil\nAuthorization: Bearer x",
                               transport=lambda _: _response())
