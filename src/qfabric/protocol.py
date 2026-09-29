"""Versioned QFabric protocol envelopes and capability negotiation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from qfabric.errors import ErrorCode, ProtocolError
from qfabric.models import ControlCommand, DeviceCapabilities, ExperimentRequest
from qfabric.version import PROTOCOL_VERSION, SUPPORTED_PROTOCOL_VERSIONS


def _ensure_aware_timestamp(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _format_timestamp(value: datetime) -> str:
    _ensure_aware_timestamp(value, "timestamp")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProtocolError(
            ErrorCode.INVALID_MESSAGE,
            f"{field_name} must be an ISO-8601 timestamp",
            details={"field": field_name},
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProtocolError(
            ErrorCode.INVALID_MESSAGE,
            f"{field_name} must be timezone-aware",
            details={"field": field_name},
        )
    return parsed


def ensure_supported_protocol_version(version: str) -> None:
    if version not in SUPPORTED_PROTOCOL_VERSIONS:
        raise ProtocolError(
            ErrorCode.UNSUPPORTED_PROTOCOL_VERSION,
            f"Unsupported protocol version {version!r}",
            details={
                "received": version,
                "supported": sorted(SUPPORTED_PROTOCOL_VERSIONS),
            },
        )


@dataclass(frozen=True, slots=True)
class CommandEnvelope:
    """Self-describing command message crossing the QFabric adapter boundary."""

    message_id: str
    device_id: str
    sent_at: datetime
    request: ExperimentRequest
    protocol_version: str = PROTOCOL_VERSION
    message_type: str = field(init=False, default="command")

    def __post_init__(self) -> None:
        if not self.message_id.strip():
            raise ValueError("message_id must be non-empty")
        if not self.device_id.strip():
            raise ValueError("device_id must be non-empty")
        if not self.protocol_version.strip():
            raise ValueError("protocol_version must be non-empty")
        _ensure_aware_timestamp(self.sent_at, "sent_at")


@dataclass(frozen=True, slots=True)
class CapabilityRequirement:
    """Minimum capabilities required by a client."""

    required_channels: frozenset[str] = field(default_factory=frozenset)
    required_calibration_keys: frozenset[str] = field(default_factory=frozenset)
    accepted_protocol_versions: frozenset[str] = field(
        default_factory=lambda: SUPPORTED_PROTOCOL_VERSIONS
    )
    requires_feedback: bool = False

    def __post_init__(self) -> None:
        if not self.accepted_protocol_versions:
            raise ValueError("accepted_protocol_versions must not be empty")


@dataclass(frozen=True, slots=True)
class CapabilityNegotiationResult:
    compatible: bool
    selected_protocol_version: str | None
    missing_channels: frozenset[str]
    missing_calibration_keys: frozenset[str]
    feedback_satisfied: bool


def _version_key(version: str) -> tuple[int, int, int]:
    try:
        major, minor, patch = version.split(".")
        return int(major), int(minor), int(patch)
    except (ValueError, AttributeError) as exc:
        raise ProtocolError(
            ErrorCode.INVALID_MESSAGE,
            f"Invalid semantic protocol version {version!r}",
            details={"version": version},
        ) from exc


def negotiate_capabilities(
    capabilities: DeviceCapabilities,
    requirement: CapabilityRequirement,
) -> CapabilityNegotiationResult:
    common_versions = (
        capabilities.protocol_versions & requirement.accepted_protocol_versions
    )
    selected = max(common_versions, key=_version_key) if common_versions else None
    missing_channels = requirement.required_channels - capabilities.supported_channels
    missing_calibration = (
        requirement.required_calibration_keys - capabilities.calibration_keys
    )
    feedback_satisfied = not requirement.requires_feedback or capabilities.supports_feedback
    compatible = (
        selected is not None
        and not missing_channels
        and not missing_calibration
        and feedback_satisfied
    )

    return CapabilityNegotiationResult(
        compatible=compatible,
        selected_protocol_version=selected,
        missing_channels=frozenset(missing_channels),
        missing_calibration_keys=frozenset(missing_calibration),
        feedback_satisfied=feedback_satisfied,
    )


_TOP_LEVEL_KEYS = {
    "message_type",
    "protocol_version",
    "message_id",
    "device_id",
    "sent_at",
    "request",
}


def command_envelope_to_dict(envelope: CommandEnvelope) -> dict[str, Any]:
    return {
        "message_type": envelope.message_type,
        "protocol_version": envelope.protocol_version,
        "message_id": envelope.message_id,
        "device_id": envelope.device_id,
        "sent_at": _format_timestamp(envelope.sent_at),
        "request": {
            "commands": [
                {
                    "channel": command.channel,
                    "value": command.value,
                    "unit": command.unit,
                    "duration_s": command.duration_s,
                    "metadata": dict(command.metadata),
                }
                for command in envelope.request.commands
            ],
            "metadata": dict(envelope.request.metadata),
        },
    }


def dumps_command_envelope(envelope: CommandEnvelope) -> str:
    ensure_supported_protocol_version(envelope.protocol_version)
    try:
        return json.dumps(
            command_envelope_to_dict(envelope),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ProtocolError(
            ErrorCode.INVALID_MESSAGE,
            "Envelope contains a value that is not JSON serializable",
        ) from exc


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProtocolError(
            ErrorCode.INVALID_MESSAGE,
            f"{field_name} must be an object",
            details={"field": field_name},
        )
    return value


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError(
            ErrorCode.INVALID_MESSAGE,
            f"{field_name} must be a non-empty string",
            details={"field": field_name},
        )
    return value


def command_envelope_from_dict(payload: Mapping[str, Any]) -> CommandEnvelope:
    unknown = set(payload) - _TOP_LEVEL_KEYS
    if unknown:
        raise ProtocolError(
            ErrorCode.INVALID_MESSAGE,
            "Unknown top-level field(s)",
            details={"unknown_fields": sorted(unknown)},
        )

    message_type = _require_string(payload.get("message_type"), "message_type")
    if message_type != "command":
        raise ProtocolError(
            ErrorCode.INVALID_MESSAGE,
            "message_type must be 'command'",
            details={"received": message_type},
        )

    protocol_version = _require_string(
        payload.get("protocol_version"), "protocol_version"
    )
    ensure_supported_protocol_version(protocol_version)

    request_payload = _require_mapping(payload.get("request"), "request")
    commands_payload = request_payload.get("commands")
    if not isinstance(commands_payload, list) or not commands_payload:
        raise ProtocolError(
            ErrorCode.INVALID_MESSAGE,
            "request.commands must be a non-empty array",
            details={"field": "request.commands"},
        )

    commands: list[ControlCommand] = []
    for index, raw_command in enumerate(commands_payload):
        command_payload = _require_mapping(
            raw_command, f"request.commands[{index}]"
        )
        value = command_payload.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ProtocolError(
                ErrorCode.INVALID_MESSAGE,
                "command.value must be numeric",
                details={"index": index},
            )
        duration = command_payload.get("duration_s")
        if duration is not None and (
            isinstance(duration, bool) or not isinstance(duration, (int, float))
        ):
            raise ProtocolError(
                ErrorCode.INVALID_MESSAGE,
                "command.duration_s must be numeric or null",
                details={"index": index},
            )
        metadata = _require_mapping(
            command_payload.get("metadata", {}),
            f"request.commands[{index}].metadata",
        )
        commands.append(
            ControlCommand(
                channel=_require_string(
                    command_payload.get("channel"),
                    f"request.commands[{index}].channel",
                ),
                value=float(value),
                unit=_require_string(
                    command_payload.get("unit"),
                    f"request.commands[{index}].unit",
                ),
                duration_s=float(duration) if duration is not None else None,
                metadata=dict(metadata),
            )
        )

    request_metadata = _require_mapping(
        request_payload.get("metadata", {}),
        "request.metadata",
    )

    return CommandEnvelope(
        message_id=_require_string(payload.get("message_id"), "message_id"),
        device_id=_require_string(payload.get("device_id"), "device_id"),
        sent_at=_parse_timestamp(
            _require_string(payload.get("sent_at"), "sent_at"),
            "sent_at",
        ),
        request=ExperimentRequest(
            commands=tuple(commands),
            metadata=dict(request_metadata),
        ),
        protocol_version=protocol_version,
    )


def loads_command_envelope(payload: str) -> CommandEnvelope:
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ProtocolError(
            ErrorCode.INVALID_MESSAGE,
            "Payload is not valid JSON",
        ) from exc
    return command_envelope_from_dict(_require_mapping(parsed, "payload"))
