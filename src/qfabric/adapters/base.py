"""Adapter contract between QFabric and concrete hardware backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

from qfabric.models import (
    CalibrationRecord,
    ControlCommand,
    DeviceCapabilities,
    ExperimentRequest,
    ExperimentResult,
    TelemetrySample,
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

    def validate_command(self, command: ControlCommand) -> None:
        if command.channel not in self.capabilities.supported_channels:
            raise ValueError(
                f"Unsupported channel {command.channel!r}; "
                f"supported={sorted(self.capabilities.supported_channels)!r}"
            )

    def validate_request(self, request: ExperimentRequest) -> None:
        for command in request.commands:
            self.validate_command(command)

    @abstractmethod
    def apply_calibration(self, calibration: CalibrationRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def execute(self, request: ExperimentRequest) -> ExperimentResult:
        raise NotImplementedError

    @abstractmethod
    def read_telemetry(self) -> tuple[TelemetrySample, ...]:
        raise NotImplementedError
