"""Disallow false protocol interoperability claims and malformed Python mappings."""

from __future__ import annotations

import pytest

from qfabric.errors import ErrorCode, ProtocolError
from qfabric.models import DeviceCapabilities, HardwareKind
from qfabric.protocol import (
    CapabilityRequirement,
    command_envelope_from_dict,
    negotiate_capabilities,
)
from qfabric.version import PROTOCOL_VERSION


def _caps(*versions: str) -> DeviceCapabilities:
    return DeviceCapabilities(
        hardware_kind=HardwareKind.GENERIC,
        supported_channels=frozenset({"drive"}),
        protocol_versions=frozenset(versions),
    )


def test_shared_unsupported_version_is_not_a_compatible_negotiation() -> None:
    result = negotiate_capabilities(
        _caps("99.0.0"),
        CapabilityRequirement(accepted_protocol_versions=frozenset({"99.0.0"})),
    )
    assert result.compatible is False
    assert result.selected_protocol_version is None


def test_unsupported_version_does_not_override_supported_negotiation() -> None:
    result = negotiate_capabilities(
        _caps(PROTOCOL_VERSION, "99.0.0"),
        CapabilityRequirement(
            accepted_protocol_versions=frozenset({PROTOCOL_VERSION, "99.0.0"})
        ),
    )
    assert result.compatible is True
    assert result.selected_protocol_version == PROTOCOL_VERSION


def _payload() -> dict:
    return {
        "message_type": "command",
        "protocol_version": PROTOCOL_VERSION,
        "message_id": "dict-keys-test",
        "device_id": "sim-001",
        "sent_at": "2026-10-19T00:00:00Z",
        "request": {
            "commands": [
                {
                    "channel": "drive",
                    "value": 0.5,
                    "unit": "arb",
                    "duration_s": None,
                    "metadata": {},
                }
            ],
            "metadata": {},
        },
    }


@pytest.mark.parametrize("location", ["root", "request", "command", "request_metadata"])
def test_direct_mapping_non_string_keys_raise_protocol_error(location: str) -> None:
    payload = _payload()
    if location == "root":
        payload[3] = "untrusted"
    elif location == "request":
        payload["request"][3] = "untrusted"
    elif location == "command":
        payload["request"]["commands"][0][3] = "untrusted"
    else:
        payload["request"]["metadata"][3] = "untrusted"
    with pytest.raises(ProtocolError) as exc:
        command_envelope_from_dict(payload)
    assert exc.value.code == ErrorCode.INVALID_MESSAGE


def test_direct_mapping_valid_payload_remains_supported() -> None:
    result = command_envelope_from_dict(_payload())
    assert result.message_id == "dict-keys-test"
    assert result.request.commands[0].value == 0.5
