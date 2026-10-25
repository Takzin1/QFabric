"""The committed cross-language golden file must match the current gate."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "fixtures" / "research_gate_golden.json"


def _exporter():
    spec = importlib.util.spec_from_file_location(
        "export_gate_golden", ROOT / "scripts" / "export_gate_golden.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_golden_cases_match_current_gate() -> None:
    assert json.loads(GOLDEN.read_text(encoding="utf-8")) == _exporter().build()


def test_golden_covers_accept_reject_and_refusal_paths() -> None:
    doc = _exporter().build()
    outcomes = [case["expected"] for case in doc["assessments"]]
    statuses = {o["value"]["status"] for o in outcomes if o["ok"]}
    assert statuses == {"ready_for_review", "rejected"}
    assert sum(not o["ok"] for o in outcomes) >= 20
    assert any(not r["expected"]["ok"] for r in doc["reviews"])
