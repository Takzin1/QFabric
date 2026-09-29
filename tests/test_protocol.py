from datetime import datetime, timezone

import pytest

from qfabric.adapters import DeterministicSimulatorAdapter
from qfabric.errors import ErrorCode, ProtocolError, ValidationError
from qfabric.models import ControlCommand, ExperimentRequest
from qfabric.protocol import (
    CapabilityRequirement,
    CommandEnvelope,
    dumps_command_envelope,
    loads_command_envelope,
)
from qfabric.version import PROTOCOL_VERSION


def _request() -> ExperimentRequest:
    return ExperimentRequest(
        commands=(
            ControlCommand(
                channel="drive",
                value=0.75,
                unit="arb",
                duration_s=1e-6,
                metadata={"phase": 0.25},
            ),
        ),
        metadata={"purpose": "protocol-test"},
    )


def _envelope(**overrides: object) -> CommandEnvelope:
    values = {
        "message_id": "msg-001",
        "device_id": "sim-001",
        "sent_at": datetime(2026, 9, 29, 4, 5, tzinfo=timezone.utc),
        "request": _request(),
        "protocol_version": PROTOCOL_VERSION,
    }
    values.update(overrides)
    return CommandEnvelope(**values)  # type: ignore[arg-type]


def test_command_envelope_json_round_trip_is_deterministic() -> None:
    envelope = _envelope()

    encoded = dumps_command_envelope(envelope)
    decoded = loads_command_envelope(encoded)

    assert dumps_command_envelope(decoded) == encoded
    assert decoded.message_id == envelope.message_id
    assert decoded.request.commands[0].channel == "drive"
    assert decoded.request.commands[0].metadata["phase"] == 0.25


def test_decoder_rejects_unknown_protocol_version() -> None:
    encoded = dumps_command_envelope(_envelope())
    tampered = encoded.replace(
        f'"protocol_version":"{PROTOCOL_VERSION}"',
        '"protocol_version":"99.0.0"',
    )

    with pytest.raises(ProtocolError) as exc_info:
        loads_command_envelope(tampered)

    assert exc_info.value.code is ErrorCode.UNSUPPORTED_PROTOCOL_VERSION


def test_adapter_rejects_envelope_for_another_device() -> None:
    adapter = DeterministicSimulatorAdapter()

    with pytest.raises(ValidationError) as exc_info:
        adapter.execute_envelope(_envelope(device_id="not-this-device"))

    assert exc_info.value.code is ErrorCode.DEVICE_MISMATCH


def test_capability_negotiation_reports_missing_requirements() -> None:
    adapter = DeterministicSimulatorAdapter()
    result = adapter.negotiate(
        CapabilityRequirement(
            required_channels=frozenset({"drive", "readout"}),
            required_calibration_keys=frozenset({"gain"}),
        )
    )

    assert result.compatible is False
    assert result.selected_protocol_version == PROTOCOL_VERSION
    assert result.missing_channels == frozenset({"readout"})


def test_capability_negotiation_succeeds_for_supported_contract() -> None:
    adapter = DeterministicSimulatorAdapter()
    result = adapter.negotiate(
        CapabilityRequirement(
            required_channels=frozenset({"drive"}),
            required_calibration_keys=frozenset({"gain"}),
        )
    )

    assert result.compatible is True
    assert result.selected_protocol_version == PROTOCOL_VERSION
    assert not result.missing_channels
    assert not result.missing_calibration_keys


def test_command_envelope_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _envelope(sent_at=datetime(2026, 9, 29, 4, 5))
