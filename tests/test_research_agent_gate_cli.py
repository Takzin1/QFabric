"""End-to-end local CLI workflow, using no model API or physical device."""

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "research_agent_gate.py"
SPEC = importlib.util.spec_from_file_location("research_agent_gate", SCRIPT)
assert SPEC and SPEC.loader
agent_cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agent_cli)

FIXTURE = Path(__file__).parent / "fixtures" / "crystaltwin_snapshot.synthetic.json"


def test_cli_full_workflow_explicit_fixture_then_self_attested_review(tmp_path) -> None:
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_bytes(FIXTURE.read_bytes())
    proposal = tmp_path / "proposal.json"
    assessment = tmp_path / "assessment.json"
    review = tmp_path / "review.json"
    assert agent_cli.main([
        "prepare", str(snapshot), str(proposal),
        "--parameter", "coolingRate", "--value", "0.2",
    ]) == 0
    prepared = json.loads(proposal.read_text())
    assert prepared["source"]["origin"] == "synthetic_fixture"
    assert prepared["source"]["modelLabel"] == "none"
    assert agent_cli.main([
        "assess", str(snapshot), str(proposal), str(assessment),
    ]) == 0
    assert json.loads(assessment.read_text())["status"] == "ready_for_review"
    assert agent_cli.main([
        "review", str(snapshot), str(proposal), str(assessment),
        str(review), "--reviewer-label", "demo-human", "--decision", "approve",
    ]) == 1
    assert not review.exists()
    assert agent_cli.main([
        "review", str(snapshot), str(proposal), str(assessment),
        str(review), "--reviewer-label", "demo-human", "--decision", "approve",
        "--attest-educational-only",
    ]) == 0
    result = json.loads(review.read_text())
    assert result["status"] == "approved_for_manual_simulation"
    assert result["simulationInput"]["coolingRate"] == 0.2
    assert result["automaticExecution"] is False
    assert result["hardwareDispatchAllowed"] is False


def test_cli_rejected_proposal_exit_code_is_not_success(tmp_path) -> None:
    proposed = tmp_path / "proposal.json"
    assessed = tmp_path / "assessment.json"
    assert agent_cli.main([
        "prepare", str(FIXTURE), str(proposed),
        "--parameter", "coolingRate", "--value", "9.0",
    ]) == 0
    assert agent_cli.main([
        "assess", str(FIXTURE), str(proposed), str(assessed),
    ]) == 2
    assert json.loads(assessed.read_text())["proposedInput"] is None
