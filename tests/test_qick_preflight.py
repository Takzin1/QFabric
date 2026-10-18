"""QICK plan preflight regression tests; no vendor SDK or hardware is used."""

from datetime import UTC, datetime

import pytest

from qfabric.errors import ErrorCode, ValidationError
from qfabric.models import ControlCommand, ExperimentRequest
from qfabric.profiles.qick import QickGeneratorBinding, QickPlanAdapter
from qfabric.protocol import CommandEnvelope


def _pulse(
    *, channel: str = "drive", value: float = 0.5,
    duration_s: float = 1e-6, frequency_mhz: float = 100.0,
    phase_deg: float = 0.0, time_us: float = 0.0,
) -> ControlCommand:
    return ControlCommand(
        channel=channel,
        value=value,
        unit="normalized_gain",
        duration_s=duration_s,
        metadata={
            "qick.frequency_mhz": frequency_mhz,
            "qick.phase_deg": phase_deg,
            "qick.time_us": time_us,
        },
    )


def _compile(*commands: ControlCommand):
    adapter = QickPlanAdapter(
        device_id="preflight-001",
        bindings=(
            QickGeneratorBinding(logical_channel="drive", gen_ch=0),
            QickGeneratorBinding(logical_channel="aux", gen_ch=1),
        ),
    )
    return adapter.compile(
        CommandEnvelope(
            device_id=adapter.device_id,
            message_id="preflight-001",
            sent_at=datetime(2026, 10, 18, tzinfo=UTC),
            request=ExperimentRequest(commands=commands),
        )
    )


@pytest.mark.parametrize(
    ("field", "number"),
    [
        ("value", float("nan")),
        ("value", float("inf")),
        ("duration_s", float("nan")),
        ("duration_s", float("inf")),
        ("frequency_mhz", float("nan")),
        ("frequency_mhz", float("inf")),
        ("phase_deg", float("-inf")),
        ("time_us", float("nan")),
        ("time_us", float("inf")),
    ],
)
def test_rejects_nonfinite_command_values(field: str, number: float) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _compile(_pulse(**{field: number}))
    assert exc_info.value.code is ErrorCode.INVALID_MESSAGE


@pytest.mark.parametrize(
    "field", ["frequency_mhz", "phase_deg", "time_us"],
)
def test_rejects_boolean_numeric_metadata(field: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _compile(_pulse(**{field: True}))
    assert exc_info.value.code is ErrorCode.INVALID_MESSAGE


def test_rejects_overflow_when_converting_seconds_to_microseconds() -> None:
    with pytest.raises(ValidationError, match="microseconds"):
        _compile(_pulse(duration_s=1e308))


def test_rejects_unrepresentable_end_time() -> None:
    with pytest.raises(ValidationError, match="end time"):
        _compile(_pulse(time_us=1e308))


def test_rejects_overlap_on_same_generator() -> None:
    with pytest.raises(ValidationError, match="Overlapping") as exc_info:
        _compile(
            _pulse(time_us=2.0, duration_s=3e-6),
            _pulse(time_us=4.0, duration_s=1e-6),
        )
    assert exc_info.value.code is ErrorCode.INVALID_MESSAGE
    assert exc_info.value.details["previous_index"] == 0
    assert exc_info.value.details["generator_channel"] == 0


def test_rejects_identical_start_times_on_same_generator() -> None:
    with pytest.raises(ValidationError, match="Overlapping"):
        _compile(_pulse(), _pulse())


def test_allows_adjacent_pulses_on_same_generator() -> None:
    plan = _compile(_pulse(), _pulse(time_us=1.0))
    assert [call.method for call in plan.calls].count("pulse") == 2


def test_allows_overlapping_pulses_on_distinct_generators() -> None:
    plan = _compile(_pulse(), _pulse(channel="aux"))
    assert [call.method for call in plan.calls].count("pulse") == 2


@pytest.mark.parametrize(
    ("gen_ch", "nqz"),
    [(True, 1), (0, False), (0.5, 1), (0, 1.5)],
)
def test_binding_rejects_noninteger_channels(gen_ch, nqz) -> None:
    with pytest.raises(ValueError, match="integer"):
        QickGeneratorBinding(logical_channel="drive", gen_ch=gen_ch, nqz=nqz)
