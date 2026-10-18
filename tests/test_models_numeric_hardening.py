"""Direct-Python regression tests for numeric safety and model invariants."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from qfabric.models import (
    CalibrationParameter,
    CalibrationProvenance,
    CalibrationRecord,
    ControlCommand,
    TelemetrySample,
)

BAD_NUMBERS = [float("nan"), float("inf"), float("-inf"), True, 10**400, "1.25"]


@pytest.mark.parametrize("value", BAD_NUMBERS)
def test_control_command_refuses_invalid_direct_value(value: object) -> None:
    with pytest.raises((ValueError, TypeError)):
        ControlCommand(channel="drive", value=value, unit="arb")  # type: ignore[arg-type]


@pytest.mark.parametrize("duration", [*BAD_NUMBERS, -0.01])
def test_control_command_refuses_invalid_direct_duration(duration: object) -> None:
    with pytest.raises((ValueError, TypeError)):
        ControlCommand(
            channel="drive", value=0.5, unit="arb", duration_s=duration
        )  # type: ignore[arg-type]


@pytest.mark.parametrize("value", BAD_NUMBERS)
def test_calibration_parameter_refuses_invalid_direct_value(value: object) -> None:
    with pytest.raises((ValueError, TypeError)):
        CalibrationParameter(name="gain", value=value, unit="ratio")  # type: ignore[arg-type]


@pytest.mark.parametrize("uncertainty", [*BAD_NUMBERS, -0.01])
def test_calibration_parameter_refuses_invalid_uncertainty(uncertainty: object) -> None:
    with pytest.raises((ValueError, TypeError)):
        CalibrationParameter(
            name="gain", value=0.5, unit="ratio", uncertainty=uncertainty
        )  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["value", "timestamp_s"])
@pytest.mark.parametrize("number", BAD_NUMBERS)
def test_telemetry_rejects_nonfinite_or_invalid_numbers(
    field: str, number: object
) -> None:
    data = {"signal": "echo:drive", "value": 0.5, "unit": "arb", "timestamp_s": 0.0}
    data[field] = number
    with pytest.raises((ValueError, TypeError)):
        TelemetrySample(**data)  # type: ignore[arg-type]


def test_direct_domain_models_still_accept_finite_numbers() -> None:
    cmd = ControlCommand(channel="drive", value=-1.25, unit="arb", duration_s=0)
    telemetry = TelemetrySample(
        signal="echo:drive", value=cmd.value, unit=cmd.unit, timestamp_s=-0.5
    )
    cal = CalibrationParameter(name="gain", value=0.5, unit="ratio", uncertainty=0)
    record = CalibrationRecord(
        device_id="sim-001",
        version="1",
        parameters=(cal,),
        created_at=datetime(2026, 10, 19, tzinfo=UTC),
        provenance=CalibrationProvenance(source="synthetic", method="test"),
    )
    assert cmd.duration_s == 0
    assert telemetry.timestamp_s == -0.5
    assert record.parameters[0].uncertainty == 0
