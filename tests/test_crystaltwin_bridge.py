"""CPU-only integration checks; importing the bridge must not import CuPy or QICK."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "crystaltwin_bridge.py"
SPEC = importlib.util.spec_from_file_location("crystaltwin_bridge_script", SCRIPT)
assert SPEC and SPEC.loader
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


def _snapshot() -> dict:
    return {
        "schemaVersion": "crystaltwin-qfabric-snapshot/1",
        "kind": "educational_snapshot",
        "source": {
            "repository": "Takzin1/crystaltwinai",
            "provenance": "synthetic",
            "mode": "educational_simulation",
        },
        "input": {
            "temperature": 65.0, "concentration": 0.4,
            "stirringSpeed": 300.0, "coolingRate": 0.5,
            "impurityLevel": 0.4, "timeSteps": 2,
        },
        "summary": {
            "avgGrowthRate": 2.0, "stabilityScore": 78.0,
            "qualityScore": 80.0, "finalYield": 4.0,
            "maxSupersaturation": 1.12, "nucleationEvents": 0,
        },
        "trajectory": [
            {"step": 1, "temperature": 64.5, "concentration": 0.4,
             "growthRate": 1.5, "crystalYield": 1.5},
            {"step": 2, "temperature": 64.0, "concentration": 0.39,
             "growthRate": 2.5, "crystalYield": 4.0},
        ],
    }


def _encoded(data: dict) -> bytes:
    return json.dumps(data).encode()


def test_cpu_pipeline_compiles_plan_without_executing_hardware() -> None:
    report = bridge.make_report(_encoded(_snapshot()), shots=256)
    assert report["schemaVersion"] == "qfabric-crystaltwin-report/1"
    assert report["qfabric"]["hardwareExecuted"] is False
    assert report["qfabric"]["mode"] == "plan_only"
    assert report["qfabric"]["readoutStatus"] == "intent_only"
    assert [call["method"] for call in report["qfabric"]["plan"]["calls"]] == [
        "declare_gen", "add_pulse", "pulse",
    ]
    assert report["snapshot"]["rowCount"] == 2
    assert report["analytics"]["backend"] == "cpu"
    assert report["analytics"]["physicalMeasurement"] is False
    assert report["analytics"]["meanPower"] == pytest.approx(1.0, abs=1e-12)
    assert len(report["source"]["sha256"]) == 64


@pytest.mark.parametrize(
    "mutation",
    [
        lambda data: data["source"].update(provenance="measured"),
        lambda data: data["input"].update(temperature=float("nan")),
        lambda data: data["summary"].update(qualityScore=float("inf")),
        lambda data: data["trajectory"][1].update(step=1),
        lambda data: data["trajectory"][1].update(temperature=float("nan")),
        lambda data: data["trajectory"].pop(),
        lambda data: data.update(schemaVersion="unknown"),
    ],
)
def test_rejects_invalid_or_mislabelled_data(mutation) -> None:
    data = _snapshot()
    mutation(data)
    with pytest.raises(ValueError):
        bridge.make_report(_encoded(data), shots=128)


def test_rejects_oversized_snapshot_and_invalid_shots() -> None:
    with pytest.raises(ValueError, match="512 KiB"):
        bridge.make_report(b" " * (bridge.MAX_INPUT_BYTES + 1))
    with pytest.raises(ValueError, match="shots"):
        bridge.make_report(_encoded(_snapshot()), shots=0)


def test_cuda_explicit_fails_closed_when_no_gpu(monkeypatch) -> None:
    def unavailable(_shots):
        raise RuntimeError("No CUDA GPU is available")

    monkeypatch.setattr(bridge, "_cuda_iq", unavailable)
    with pytest.raises(RuntimeError, match="No CUDA GPU"):
        bridge.analyze_iq(256, "cuda")
    result = bridge.analyze_iq(256, "auto")
    assert result["backend"] == "cpu"


def test_snapshot_source_hash_is_sha256_of_exact_input_bytes() -> None:
    raw = _encoded(_snapshot())
    report = bridge.make_report(raw, shots=8)
    import hashlib

    assert report["source"]["sha256"] == hashlib.sha256(raw).hexdigest()
