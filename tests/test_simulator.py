from datetime import UTC, datetime

import pytest

from qfabric.adapters import DeterministicSimulatorAdapter
from qfabric.errors import ErrorCode, ValidationError
from qfabric.models import (
    CalibrationParameter,
    CalibrationProvenance,
    CalibrationRecord,
    ControlCommand,
    ExperimentRequest,
)


def test_execute_round_trips_supported_commands() -> None:
    adapter = DeterministicSimulatorAdapter()
    request = ExperimentRequest(
        commands=(
            ControlCommand(channel="drive", value=1.25, unit="arb", duration_s=1e-6),
            ControlCommand(channel="detune", value=-0.5, unit="arb"),
        )
    )

    result = adapter.execute(request)

    assert result.completed is True
    assert result.device_id == "sim-001"
    assert [sample.value for sample in result.measurements] == [1.25, -0.5]
    assert adapter.read_telemetry() == result.measurements


def test_rejects_unsupported_channel_with_stable_error_code() -> None:
    adapter = DeterministicSimulatorAdapter()
    request = ExperimentRequest(
        commands=(ControlCommand(channel="not-real", value=1.0, unit="arb"),)
    )

    with pytest.raises(ValidationError) as exc_info:
        adapter.execute(request)

    assert exc_info.value.code is ErrorCode.UNSUPPORTED_CHANNEL


def test_calibration_is_device_scoped_and_capability_checked() -> None:
    adapter = DeterministicSimulatorAdapter()
    calibration = CalibrationRecord(
        device_id=adapter.device_id,
        version="cal-001",
        parameters=(
            CalibrationParameter(name="gain", value=0.99, unit="ratio", uncertainty=0.01),
        ),
        created_at=datetime(2026, 9, 29, 4, 0, tzinfo=UTC),
        provenance=CalibrationProvenance(
            source="qfabric-test",
            method="deterministic-reference",
        ),
    )

    adapter.apply_calibration(calibration)

    assert adapter.calibration == calibration


def test_rejects_calibration_for_another_device() -> None:
    adapter = DeterministicSimulatorAdapter()
    calibration = CalibrationRecord(
        device_id="other-device",
        version="cal-001",
        parameters=(CalibrationParameter(name="gain", value=1.0, unit="ratio"),),
        created_at=datetime(2026, 9, 29, 4, 0, tzinfo=UTC),
        provenance=CalibrationProvenance(
            source="qfabric-test",
            method="deterministic-reference",
        ),
    )

    with pytest.raises(ValidationError) as exc_info:
        adapter.apply_calibration(calibration)

    assert exc_info.value.code is ErrorCode.DEVICE_MISMATCH
