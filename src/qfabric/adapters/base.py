"""Adapter contract between QFabric and concrete hardware backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

from qfabric.errors import ErrorCode, ProtocolError, ValidationError
from qfabric.models import (
    CalibrationRecord,
    ControlCommand,
    DeviceCapabilities,
    ExperimentRequest,
    ExperimentResult,
    TelemetrySample,
)
from qfabric.protocol import (
    CapabilityNegotiationResult,
    CapabilityRequirement,
    CommandEnvelope,
    ensure_supported_protocol_version,
    negotiate_capabilities,
)


class DeviceAdapter(ABC):
    """Contract implemented by each physical or simulated hardware backend."""

    @property
    @abstractmethod
    def device_id(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def capabilities(self) -> DeviceCapabilities:
        raise NotImplementedError

    def negotiate(
        self,
        requirement: CapabilityRequirement,
    ) -> CapabilityNegotiationResult:
        return negotiate_capabilities(self.capabilities, requirement)

    def validate_command(self, command: ControlCommand) -> None:
        if command.channel not in self.capabilities.supported_channels:
            raise ValidationError(
                ErrorCode.UNSUPPORTED_CHANNEL,
                f"Unsupported channel {command.channel!r}",
                details={
                    "channel": command.channel,
                    "supported": sorted(self.capabilities.supported_channels),
                },
            )

    def validate_request(self, request: ExperimentRequest) -> None:
        for command in request.commands:
            self.validate_command(command)

    def execute_envelope(self, envelope: CommandEnvelope) -> ExperimentResult:
        ensure_supported_protocol_version(envelope.protocol_version)
        if envelope.protocol_version not in self.capabilities.protocol_versions:
            raise ProtocolError(
                ErrorCode.UNSUPPORTED_PROTOCOL_VERSION,
                "Adapter does not advertise the envelope protocol version",
                details={
                    "received": envelope.protocol_version,
                    "adapter_supported": sorted(self.capabilities.protocol_versions),
                },
            )
        if envelope.device_id != self.device_id:
            raise ValidationError(
                ErrorCode.DEVICE_MISMATCH,
                "Command envelope targets a different device",
                details={
                    "target": envelope.device_id,
                    "adapter_device_id": self.device_id,
                },
            )
        return self.execute(envelope.request)

    @abstractmethod
    def apply_calibration(self, calibration: CalibrationRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def execute(self, request: ExperimentRequest) -> ExperimentResult:
        raise NotImplementedError

    @abstractmethod
    def read_telemetry(self) -> tuple[TelemetrySample, ...]:
        raise NotImplementedError
