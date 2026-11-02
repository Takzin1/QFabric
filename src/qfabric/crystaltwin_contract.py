"""Shared, conservative CrystalTwinAI synthetic-snapshot semantic contract.

Structural consistency is NOT evidence of experimental provenance, scientific
model validity, quantum readout, or correct source authorship. The historical
two-step synthetic fixture remains supported; new UI runs use 10..200 steps.
This module never invokes an experiment or hardware SDK.
"""

from __future__ import annotations

import math
from typing import Any

INPUT_BOUNDS = {
    "temperature": (20.0, 90.0),
    "concentration": (0.1, 0.6),
    "stirringSpeed": (0.0, 1000.0),
    "coolingRate": (0.05, 2.0),
    "impurityLevel": (0.0, 5.0),
}


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} requires a finite number")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} requires a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} requires a finite number")
    return number


def validate_snapshot_semantics(snapshot: dict[str, Any]) -> None:
    """Fail closed on implausible or self-contradictory synthetic reports.

    This must be called AFTER callers check version, exact object shape and
    source label. No attempt is made to rerun the CrystalTwinAI simulator.
    """
    inputs = snapshot["input"]
    summary = snapshot["summary"]
    rows = snapshot["trajectory"]
    for field, (low, high) in INPUT_BOUNDS.items():
        number = _finite(inputs[field], "input." + field)
        if not low <= number <= high:
            raise ValueError(f"input.{field} outside educational input bounds")
    steps = _finite(inputs["timeSteps"], "input.timeSteps")
    if not steps.is_integer() or int(steps) not in {2, *range(10, 201)}:
        raise ValueError("timeSteps must be 10..200 or legacy synthetic fixture length 2")
    if len(rows) != int(steps):
        raise ValueError("trajectory length differs from timeSteps")

    prev_temp = _finite(inputs["temperature"], "input.temperature")
    prev_concentration = _finite(inputs["concentration"], "input.concentration")
    prev_yield = 0.0
    growth_total = 0.0
    for index, row in enumerate(rows):
        if type(row["step"]) is not int or row["step"] != index + 1:
            raise ValueError("trajectory steps must be contiguous and start at 1")
        temperature = _finite(row["temperature"], "trajectory.temperature")
        concentration = _finite(row["concentration"], "trajectory.concentration")
        growth = _finite(row["growthRate"], "trajectory.growthRate")
        yield_value = _finite(row["crystalYield"], "trajectory.crystalYield")
        if not 0 <= temperature <= prev_temp + 1e-9:
            raise ValueError("trajectory temperature must be bounded and nonincreasing")
        if not 0 <= concentration <= min(1.0, prev_concentration + 1e-9):
            raise ValueError("trajectory concentration must be bounded and nonincreasing")
        if growth < 0:
            raise ValueError("trajectory growth rate cannot be negative")
        if not prev_yield - 1e-9 <= yield_value <= 100:
            raise ValueError("trajectory yield must be bounded and nondecreasing")
        prev_temp, prev_concentration, prev_yield = temperature, concentration, yield_value
        growth_total += growth

    for field in ("qualityScore", "stabilityScore", "finalYield"):
        number = _finite(summary[field], "summary." + field)
        if not 0 <= number <= 100:
            raise ValueError(f"summary.{field} must be 0..100")
    if not math.isclose(
        _finite(summary["finalYield"], "summary.finalYield"),
        prev_yield, rel_tol=1e-9, abs_tol=1e-8,
    ):
        raise ValueError("finalYield conflicts with final trajectory row")
    if not math.isclose(
        _finite(summary["avgGrowthRate"], "summary.avgGrowthRate"),
        growth_total / len(rows), rel_tol=1e-9, abs_tol=1e-8,
    ):
        raise ValueError("avgGrowthRate conflicts with trajectory")
    if _finite(summary["maxSupersaturation"], "summary.maxSupersaturation") < 0:
        raise ValueError("maxSupersaturation cannot be negative")
    events = summary["nucleationEvents"]
    if type(events) is not int or not 0 <= events <= len(rows):
        raise ValueError("nucleationEvents must be a bounded integer")
