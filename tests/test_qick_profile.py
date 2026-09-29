from datetime import UTC, datetime

import pytest

from qfabric.errors import ErrorCode, ValidationError
from qfabric.models import ControlCommand, ExperimentRequest
from qfabric.profiles.qick import (
    QICK_PROFILE_VERSION,
    QICK_REFERENCE_COMMIT,
    QickGeneratorBinding,
    QickPlanAdapter,
)
from qfabric.protocol import CommandEnvelope


def _adapter() -> QickPlanAdapter:
    return QickPlanAdapter(
        device_id="qick-lab-01",
        bindings=(
            QickGeneratorBinding(logical_channel="drive", gen_ch=0, nqz=1),
            QickGeneratorBinding(logical_channel="aux", gen_ch=1, nqz=2),
        ),
    )


def _envelope(*commands: ControlCommand, device_id: str = "qick-lab-01") -> CommandEnvelope:
    return CommandEnvelope(
        message_id="msg-qick-001",
        device_id=device_id,
        sent_at=datetime(2026, 9, 29, 4, 15, tzinfo=UTC),
        request=ExperimentRequest(commands=commands),
    )


def _pulse(
    *,
    channel: str = "drive",
    gain: float = 0.5,
    unit: str = "normalized_gain",
    duration_s: float = 1e-6,
    frequency_mhz: float = 100.0,
    phase_deg: float = 0.0,
    time_us: float = 0.0,
    style: str = "const",
) -> ControlCommand:
    return ControlCommand(
        channel=channel,
        value=gain,
        unit=unit,
        duration_s=duration_s,
        metadata={
            "qick.frequency_mhz": frequency_mhz,
            "qick.phase_deg": phase_deg,
            "qick.time_us": time_us,
            "qick.style": style,
        },
    )


def test_compiles_const_pulse_to_pinned_qick_call_plan() -> None:
    plan = _adapter().compile(_envelope(_pulse()))

    assert plan.profile_version == QICK_PROFILE_VERSION
    assert plan.qick_reference_commit == QICK_REFERENCE_COMMIT
    assert [call.method for call in plan.calls] == [
        "declare_gen",
        "add_pulse",
        "pulse",
    ]
    assert dict(plan.calls[0].kwargs) == {"ch": 0, "nqz": 1}
    assert dict(plan.calls[1].kwargs) == {
        "ch": 0,
        "name": "qf_0000",
        "style": "const",
        "freq": 100.0,
        "phase": 0.0,
        "gain": 0.5,
        "length": 1.0,
    }
    assert dict(plan.calls[2].kwargs) == {
        "ch": 0,
        "name": "qf_0000",
        "t": 0.0,
    }


def test_declares_each_generator_once_and_keeps_deterministic_names() -> None:
    plan = _adapter().compile(
        _envelope(
            _pulse(channel="drive", time_us=0.0),
            _pulse(channel="drive", time_us=2.0),
            _pulse(channel="aux", time_us=4.0),
        )
    )

    assert [call.method for call in plan.calls] == [
        "declare_gen",
        "add_pulse",
        "pulse",
        "add_pulse",
        "pulse",
        "declare_gen",
        "add_pulse",
        "pulse",
    ]
    pulse_names = [
        call.kwargs["name"]
        for call in plan.calls
        if call.method == "add_pulse"
    ]
    assert pulse_names == ["qf_0000", "qf_0001", "qf_0002"]


def test_rejects_unbound_logical_channel() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _adapter().compile(_envelope(_pulse(channel="readout")))

    assert exc_info.value.code is ErrorCode.CAPABILITY_MISMATCH


def test_rejects_wrong_device_target() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _adapter().compile(
            _envelope(_pulse(), device_id="different-device")
        )

    assert exc_info.value.code is ErrorCode.DEVICE_MISMATCH


@pytest.mark.parametrize(
    ("command", "expected_code"),
    [
        (_pulse(unit="arb"), ErrorCode.CAPABILITY_MISMATCH),
        (_pulse(gain=1.1), ErrorCode.INVALID_MESSAGE),
        (_pulse(style="arb"), ErrorCode.CAPABILITY_MISMATCH),
        (_pulse(duration_s=0.0), ErrorCode.INVALID_MESSAGE),
    ],
)
def test_rejects_ambiguous_or_unsupported_pulse_semantics(
    command: ControlCommand,
    expected_code: ErrorCode,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _adapter().compile(_envelope(command))

    assert exc_info.value.code is expected_code


def test_rejects_missing_required_qick_schedule_metadata() -> None:
    command = ControlCommand(
        channel="drive",
        value=0.5,
        unit="normalized_gain",
        duration_s=1e-6,
        metadata={"qick.frequency_mhz": 100.0},
    )

    with pytest.raises(ValidationError) as exc_info:
        _adapter().compile(_envelope(command))

    assert exc_info.value.code is ErrorCode.INVALID_MESSAGE


def test_plan_is_plain_data_and_requires_no_qick_dependency() -> None:
    plan = _adapter().compile(_envelope(_pulse()))
    payload = plan.to_dict()

    assert payload["qick_reference_commit"] == QICK_REFERENCE_COMMIT
    assert payload["calls"][1]["method"] == "add_pulse"
    assert payload["calls"][1]["kwargs"]["freq"] == 100.0
