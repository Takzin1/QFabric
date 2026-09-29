from qfabric.adapters import DeterministicSimulatorAdapter
from qfabric.models import (
    CalibrationParameter,
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


def test_rejects_unsupported_channel() -> None:
    adapter = DeterministicSimulatorAdapter()
    request = ExperimentRequest(
        commands=(ControlCommand(channel="not-real", value=1.0, unit="arb"),)
    )

    try:
        adapter.execute(request)
    except ValueError as exc:
        assert "Unsupported channel" in str(exc)
    else:
        raise AssertionError("unsupported command should be rejected")


def test_calibration_is_device_scoped_and_capability_checked() -> None:
    adapter = DeterministicSimulatorAdapter()
    calibration = CalibrationRecord(
        device_id=adapter.device_id,
        version="cal-001",
        parameters=(
            CalibrationParameter(name="gain", value=0.99, unit="ratio", uncertainty=0.01),
        ),
    )

    adapter.apply_calibration(calibration)

    assert adapter.calibration == calibration
