"""Shared offline snapshot semantics must match bridge and proposal-gate policy."""

import importlib.util
import json
from pathlib import Path

import pytest

from qfabric.crystaltwin_contract import validate_snapshot_semantics
from qfabric.orchestration import parse_snapshot

FIXTURE = Path(__file__).parent / "fixtures" / "crystaltwin_snapshot.synthetic.json"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "crystaltwin_bridge.py"
SPEC = importlib.util.spec_from_file_location("snapshot_bridge", SCRIPT)
assert SPEC and SPEC.loader
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


def _fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _raw(value):
    return json.dumps(value, allow_nan=False).encode("utf-8")


def test_original_legacy_fixture_passes_both_contracts():
    data = _fixture()
    validate_snapshot_semantics(data)
    assert parse_snapshot(_raw(data)) == data
    assert bridge.validate_snapshot(data) == data


@pytest.mark.parametrize("change", [
    lambda d: d["input"].update(temperature=900),
    lambda d: d["input"].update(coolingRate=-0.5),
    lambda d: d["input"].update(timeSteps=2.5),
    lambda d: d["trajectory"][0].update(step=0),
    lambda d: d["trajectory"][1].update(step=3),
    lambda d: d["trajectory"][0].update(temperature=66),
    lambda d: d["trajectory"][1].update(concentration=0.8),
    lambda d: d["trajectory"][0].update(growthRate=-1),
    lambda d: d["trajectory"][1].update(crystalYield=1),
    lambda d: d["summary"].update(finalYield=50),
    lambda d: d["summary"].update(avgGrowthRate=50),
    lambda d: d["summary"].update(qualityScore=120),
    lambda d: d["summary"].update(nucleationEvents=2.5),
    lambda d: d["summary"].update(nucleationEvents=True),
])
def test_malformed_snapshot_fails_in_both_paths(change):
    data = _fixture()
    change(data)
    with pytest.raises((ValueError, TypeError)):
        parse_snapshot(_raw(data))
    with pytest.raises((ValueError, TypeError)):
        bridge.validate_snapshot(data)
