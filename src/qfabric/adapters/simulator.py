"""Deterministic reference adapter used for development and contract tests."""

from __future__ import annotations

from qfabric.adapters.base import DeviceAdapter
from qfabric.errors import ErrorCode, ValidationError
from qfabric.models import (
    CalibrationRecord,
    DeviceCapabilities,
    ExperimentRequest,
    ExperimentResult,
    HardwareKind,
    TelemetrySample,
)


class DeterministicSimulatorAdapter(DeviceAdapter):
    """A deterministic simulator.

    This adapter validates the QFabric contract and provides reproducible behavior
    for tests. It is deliberately not a physics simulator.
    """

    def __init__(
        self,
        device_id: str = "sim-001",
        capabilities: DeviceCapabilities | None = None,
    ) -> None:
        self._device_id = device_id
        self._capabilities = capabilities or DeviceCapabilities(
            hardware_kind=HardwareKind.GENERIC,
            supported_channels=frozenset({"drive", "detune"}),
            calibration_keys=frozenset({"gain", "offset"}),
        )
        self._calibration: CalibrationRecord | None = None
        self._telemetry: tuple[TelemetrySample, ...] = ()

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def capabilities(self) -> DeviceCapabilities:
        return self._capabilities

    @property
    def calibration(self) -> CalibrationRecord | None:
        return self._calibration

    def apply_calibration(self, calibration: CalibrationRecord) -> None:
        if calibration.device_id != self.device_id:
            raise ValidationError(
                ErrorCode.DEVICE_MISMATCH,
                "Calibration targets a different device",
                details={
                    "target": calibration.device_id,
                    "adapter_device_id": self.device_id,
                },
            )

        parameter_names = {parameter.name for parameter in calibration.parameters}
        unknown = parameter_names - self.capabilities.calibration_keys
        if unknown:
            raise ValidationError(
                ErrorCode.UNKNOWN_CALIBRATION_KEY,
                "Calibration contains unsupported parameter(s)",
                details={"unknown": sorted(unknown)},
            )

        self._calibration = calibration

    def execute(self, request: ExperimentRequest) -> ExperimentResult:
        self.validate_request(request)

        measurements = tuple(
            TelemetrySample(
                signal=f"echo:{command.channel}",
                value=command.value,
                unit=command.unit,
                timestamp_s=float(index),
            )
            for index, command in enumerate(request.commands)
        )
        self._telemetry = measurements

        return ExperimentResult(
            device_id=self.device_id,
            measurements=measurements,
            completed=True,
            metadata={"adapter": "deterministic-simulator"},
        )

    def read_telemetry(self) -> tuple[TelemetrySample, ...]:
        return self._telemetry
