"""Offline CrystalTwinAI <-> QFabric research bridge.

This demonstration NEVER accesses quantum hardware, industrial equipment, or the
network. CuPy/CUDA processing is optional and is never claimed when unavailable.
The generated IQ values are deterministic mathematical fixtures, NOT measurements.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from qfabric.models import ControlCommand, ExperimentRequest
from qfabric.profiles.qick import QickGeneratorBinding, QickPlanAdapter
from qfabric.profiles.qick_readout import QickReadoutIntent, QickReadoutPlanner
from qfabric.protocol import CommandEnvelope

SNAPSHOT_VERSION = "crystaltwin-qfabric-snapshot/1"
REPORT_VERSION = "qfabric-crystaltwin-report/1"
MAX_INPUT_BYTES = 512 * 1024
MAX_STEPS = 200
MAX_SHOTS = 2_000_000
INPUT_KEYS = frozenset({
    "temperature", "concentration", "stirringSpeed", "coolingRate",
    "impurityLevel", "timeSteps",
})
SUMMARY_KEYS = frozenset({
    "avgGrowthRate", "stabilityScore", "qualityScore", "finalYield",
    "maxSupersaturation", "nucleationEvents",
})
SERIES_KEYS = frozenset({
    "step", "temperature", "concentration", "growthRate", "crystalYield",
})


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{field} must be a JSON object")
    return value


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be numeric")
    try:
        numeric = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{field} must be finite") from exc
    if not math.isfinite(numeric):
        raise ValueError(f"{field} must be finite")
    return numeric


def validate_snapshot(data: Any) -> dict[str, Any]:
    doc = _mapping(data, "snapshot")
    if set(doc) != {"schemaVersion", "kind", "source", "input", "summary", "trajectory"}:
        raise ValueError("snapshot contains missing or unsupported top-level fields")
    if doc["schemaVersion"] != SNAPSHOT_VERSION or doc["kind"] != "educational_snapshot":
        raise ValueError("unsupported snapshot schema/kind")
    source = _mapping(doc["source"], "source")
    if source != {
        "repository": "Takzin1/crystaltwinai",
        "provenance": "synthetic",
        "mode": "educational_simulation",
    }:
        raise ValueError("bridge only accepts explicitly synthetic educational snapshots")
    control = _mapping(doc["input"], "input")
    if set(control) != INPUT_KEYS:
        raise ValueError("snapshot input fields are incomplete or unexpected")
    for key, value in control.items():
        _finite(value, f"input.{key}")
    summary = _mapping(doc["summary"], "summary")
    if set(summary) != SUMMARY_KEYS:
        raise ValueError("snapshot summary fields are incomplete or unexpected")
    for key, value in summary.items():
        _finite(value, f"summary.{key}")
    trajectory = doc["trajectory"]
    if not isinstance(trajectory, list) or not (1 <= len(trajectory) <= MAX_STEPS):
        raise ValueError("trajectory must contain 1..200 rows")
    previous_step = 0
    for index, raw in enumerate(trajectory):
        row = _mapping(raw, f"trajectory[{index}]")
        if set(row) != SERIES_KEYS:
            raise ValueError("trajectory row fields are incomplete or unexpected")
        step = row["step"]
        if isinstance(step, bool) or not isinstance(step, int) or not previous_step < step <= MAX_STEPS:
            raise ValueError("trajectory steps must be strictly increasing integers in 1..200")
        for key, value in row.items():
            if key != "step":
                _finite(value, f"trajectory[{index}].{key}")
        previous_step = step
    if not float(control["timeSteps"]).is_integer():
        raise ValueError("timeSteps must be an integer")
    if len(trajectory) != int(control["timeSteps"]):
        raise ValueError("trajectory length does not match timeSteps")
    return doc


def _cpu_iq(shots: int) -> tuple[float, float, float]:
    # Mathematical signal only. No QICK acquisition or model of a physical device.
    total_i = total_q = total_power = 0.0
    for index in range(shots):
        phase = (index % 256) * (math.tau / 256.0)
        i = math.cos(phase)
        q = math.sin(phase)
        total_i += i
        total_q += q
        total_power += i * i + q * q
    return total_i / shots, total_q / shots, total_power / shots


def _cuda_iq(shots: int) -> tuple[float, float, float]:
    try:
        import cupy as cp  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("NVIDIA CUDA mode requires an installed compatible CuPy package") from exc
    try:
        if cp.cuda.runtime.getDeviceCount() < 1:
            raise RuntimeError("No CUDA GPU is available")
        # Compute the same explicitly synthetic signal in vectorized CUDA arrays.
        indices = cp.arange(shots, dtype=cp.float64)
        phases = cp.mod(indices, 256) * (math.tau / 256.0)
        i_values, q_values = cp.cos(phases), cp.sin(phases)
        means = (
            cp.mean(i_values),
            cp.mean(q_values),
            cp.mean(i_values * i_values + q_values * q_values),
        )
        cp.cuda.Stream.null.synchronize()
        return tuple(float(item.get()) for item in means)  # type: ignore[return-value]
    except Exception as exc:
        raise RuntimeError(f"NVIDIA CUDA execution failed: {exc}") from exc


def analyze_iq(shots: int, backend: str) -> dict[str, Any]:
    if isinstance(shots, bool) or not isinstance(shots, int) or not 1 <= shots <= MAX_SHOTS:
        raise ValueError("shots must be an integer in 1..2000000")
    if backend not in {"cpu", "cuda", "auto"}:
        raise ValueError("backend must be cpu, cuda, or auto")
    started = perf_counter()
    selected = "cpu"
    if backend == "cpu":
        values = _cpu_iq(shots)
    elif backend == "cuda":
        values = _cuda_iq(shots)
        selected = "nvidia_cuda"
    else:
        # Auto fallback is explicit; never label CPU calculations as CUDA results.
        try:
            values = _cuda_iq(shots)
            selected = "nvidia_cuda"
        except RuntimeError:
            values = _cpu_iq(shots)
    elapsed_ms = (perf_counter() - started) * 1000.0
    return {
        "backend": selected,
        "signalType": "synthetic_iq",
        "algorithm": "analytic_unit_circle_v1",
        "shots": shots,
        "meanI": values[0],
        "meanQ": values[1],
        "meanPower": values[2],
        "elapsedMs": round(elapsed_ms, 3),
        "physicalMeasurement": False,
    }


def make_report(raw_snapshot: bytes, *, backend: str = "cpu", shots: int = 4096) -> dict[str, Any]:
    if len(raw_snapshot) > MAX_INPUT_BYTES:
        raise ValueError("snapshot exceeds 512 KiB")
    try:
        snapshot = validate_snapshot(json.loads(raw_snapshot))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("snapshot must be UTF-8 JSON") from exc

    # Standalone illustrative QICK control plan: intentionally independent of the
    # crystallization simulation, never an industrial or quantum measurement.
    adapter = QickPlanAdapter(
        device_id="qick-demo-no-hardware",
        bindings=(QickGeneratorBinding(logical_channel="drive", gen_ch=0),),
    )
    plan = adapter.compile(
        CommandEnvelope(
            message_id="qfabric-crystaltwin-demo",
            device_id=adapter.device_id,
            sent_at=datetime.now(UTC),
            request=ExperimentRequest(commands=(
                ControlCommand(
                    channel="drive", value=0.25, unit="normalized_gain",
                    duration_s=1e-6,
                    metadata={
                        "qick.frequency_mhz": 100.0,
                        "qick.phase_deg": 0.0,
                        "qick.time_us": 0.0,
                    },
                ),
            )),
        )
    )
    # Readout remains *intent only*; this never compiles acquisition calls.
    readout = QickReadoutPlanner(
        device_id=adapter.device_id,
        generator_channels=(0,),
        adc_channels=(0,),
    ).plan(
        QickReadoutIntent(
            device_id=adapter.device_id,
            readout_gen_ch=0,
            adc_channels=(0,),
            frequency_mhz=100.0,
            capture_length_us=1.0,
            trigger_offset_us=0.0,
            shots=shots,
        )
    )
    result = {
        "schemaVersion": REPORT_VERSION,
        "kind": "qfabric_research_bridge_report",
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source": {
            "repository": "Takzin1/crystaltwinai",
            "mode": "educational_simulation",
            "provenance": "synthetic",
            "sha256": hashlib.sha256(raw_snapshot).hexdigest(),
        },
        "snapshot": {
            "input": snapshot["input"],
            "summary": snapshot["summary"],
            "rowCount": len(snapshot["trajectory"]),
        },
        "qfabric": {
            "repository": "Takzin1/QFabric",
            "mode": "plan_only",
            "hardwareExecuted": False,
            "readoutStatus": "intent_only",
            "readoutIntent": readout.to_dict(),
            "qickReferenceCommit": plan.qick_reference_commit,
            "plan": plan.to_dict(),
        },
        "analytics": analyze_iq(shots, backend),
        "disclaimer": (
            "Synthetic educational bridge only. No physical quantum readout, "
            "crystallization measurement, process control, verified speedup, "
            "or quantum advantage is claimed."
        ),
    }
    return result



def verify_report(raw_snapshot: bytes, raw_report: bytes) -> dict[str, bool]:
    """Check exact snapshot-byte linkage and fail-closed report semantics.

    This is *not* a signature, source authentication or physical validation.
    """
    if len(raw_snapshot) > MAX_INPUT_BYTES or len(raw_report) > MAX_INPUT_BYTES:
        raise ValueError("snapshot/report exceeds 512 KiB")
    try:
        snapshot = validate_snapshot(json.loads(raw_snapshot))
        report = _mapping(json.loads(raw_report), "report")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("snapshot and report must be UTF-8 JSON") from exc

    if report.get("schemaVersion") != REPORT_VERSION or (
        report.get("kind") != "qfabric_research_bridge_report"
    ):
        raise ValueError("unsupported QFabric report schema or kind")
    source = _mapping(report.get("source"), "source")
    if (
        source.get("repository") != "Takzin1/crystaltwinai"
        or source.get("provenance") != "synthetic"
        or source.get("mode") != "educational_simulation"
        or source.get("sha256") != hashlib.sha256(raw_snapshot).hexdigest()
    ):
        raise ValueError("report source provenance or snapshot SHA-256 does not match")
    reported_snapshot = _mapping(report.get("snapshot"), "snapshot")
    if reported_snapshot != {
        "input": snapshot["input"],
        "summary": snapshot["summary"],
        "rowCount": len(snapshot["trajectory"]),
    }:
        raise ValueError("report summary/inputs do not match source snapshot")
    qfabric = _mapping(report.get("qfabric"), "qfabric")
    if (
        qfabric.get("repository") != "Takzin1/QFabric"
        or qfabric.get("mode") != "plan_only"
        or qfabric.get("hardwareExecuted") is not False
        or qfabric.get("readoutStatus") != "intent_only"
    ):
        raise ValueError("report falsely asserts quantum hardware or acquisition")
    readout = _mapping(qfabric.get("readoutIntent"), "readoutIntent")
    if (
        readout.get("kind") != "qick_readout_proposal"
        or readout.get("status") != "intent_only"
        or readout.get("provenance") != "synthetic_intent"
        or readout.get("hardwareExecuted") is not False
    ):
        raise ValueError("invalid or missing readout-intent-only claims")
    plan = _mapping(qfabric.get("plan"), "plan")
    if (
        qfabric.get("qickReferenceCommit") != plan.get("qick_reference_commit")
        or qfabric.get("qickReferenceCommit") != readout.get("qick_reference_commit")
        or plan.get("device_id") != readout.get("device_id")
    ):
        raise ValueError("inconsistent QICK profile reference/device")
    calls = plan.get("calls")
    if not isinstance(calls, list) or [x.get("method") for x in calls if isinstance(x, dict)] != [
        "declare_gen", "add_pulse", "pulse"
    ]:
        raise ValueError("unknown QICK method, plan shape or implied acquisition")
    analytics = _mapping(report.get("analytics"), "analytics")
    if (
        analytics.get("signalType") != "synthetic_iq"
        or analytics.get("algorithm") != "analytic_unit_circle_v1"
        or analytics.get("physicalMeasurement") is not False
        or analytics.get("backend") not in ("cpu", "nvidia_cuda")
    ):
        raise ValueError("analytics must be labelled synthetic with actual backend")
    shots = readout.get("shots")
    if isinstance(shots, bool) or not isinstance(shots, int) or not 1 <= shots <= MAX_SHOTS:
        raise ValueError("readout shots outside bounds")
    if analytics.get("shots") != shots or isinstance(analytics.get("shots"), bool):
        raise ValueError("analytics shots do not match readout intent")
    for key in ("meanI", "meanQ", "meanPower", "elapsedMs"):
        _finite(analytics.get(key), f"analytics.{key}")
    if analytics["meanPower"] < 0 or analytics["elapsedMs"] < 0:
        raise ValueError("negative power or duration in analytics")
    return {"snapshot_digest_match": True, "semantic_invariants_pass": True}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path, help="Exported CrystalTwinAI snapshot JSON")
    parser.add_argument("output", type=Path, help="Resulting QFabric bridge report JSON")
    parser.add_argument("--backend", choices=("cpu", "cuda", "auto"), default="cpu")
    parser.add_argument("--shots", type=int, default=4096)
    parser.add_argument(
        "--verify", action="store_true",
        help="Verify existing report against exact snapshot bytes; no new report is generated",
    )
    args = parser.parse_args(argv)
    try:
        if args.snapshot.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError("snapshot exceeds 512 KiB")
        if args.verify:
            evidence = verify_report(args.snapshot.read_bytes(), args.output.read_bytes())
            print(f"Verified report: {args.output} | checks: {evidence}")
            return 0
        report = make_report(
            args.snapshot.read_bytes(),
            backend=args.backend,
            shots=args.shots,
        )
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        print(f"Bridge failed: {exc}", file=sys.stderr)
        return 1
    print(f"Report: {args.output} | compute backend: {report['analytics']['backend']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
