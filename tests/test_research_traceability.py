"""The paper-to-code table must point at code and tests that actually exist."""

import importlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = json.loads((ROOT / "data" / "research_traceability.json").read_text(encoding="utf-8"))
FIELDS = {"id", "method", "reference", "implementation", "tests", "assumption"}


def test_every_entry_resolves_to_a_callable_and_existing_tests() -> None:
    assert TABLE["schemaVersion"] == "qfabric-research-traceability/1"
    ids = [entry["id"] for entry in TABLE["entries"]]
    assert ids == sorted(set(ids)) and all(re.fullmatch(r"TRC-[0-9]{3}", i) for i in ids)
    for entry in TABLE["entries"]:
        assert set(entry) == FIELDS
        module, name = entry["implementation"].split(":")
        assert callable(getattr(importlib.import_module(module), name))
        assert entry["tests"] and entry["reference"].strip() and entry["assumption"].strip()
        for node in entry["tests"]:
            path, test = node.split("::")
            assert f"def {test}(" in (ROOT / path).read_text(encoding="utf-8")


def test_table_does_not_claim_reproduction_of_published_results() -> None:
    text = json.dumps(TABLE).lower()
    assert "not evidence that a published result was reproduced" in text
    for claim in ("reproduces the paper", "validated on hardware", "quantum advantage"):
        assert claim not in text
