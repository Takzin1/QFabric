"""Core, vendor-neutral QFabric domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class HardwareKind(str, Enum):
    """Broad hardware families supported by the abstraction layer."""

    ION_TRAP = "ion_trap"
    NEUTRAL_ATOM = "neutral_atom"
    PHOTONIC = "photonic"
    SUPERCONDUCTING = "superconducting"
    GENERIC = "generic"


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True, slots=True)
class DeviceCapabilities:
    hardware_kind: HardwareKind
    supported_channels: frozenset[str]
    calibration_keys: frozenset[str] = field(default_factory=frozenset)
    supports_feedback: bool = False


@dataclass(frozen=True, slots=True)
class ControlCommand:
    channel: str
    value: float
    unit: str
    duration_s: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.channel.strip():
            raise ValueError("channel must be non-empty")
        if not self.unit.strip():
            raise ValueError("unit must be non-empty")
        if self.duration_s is not None and self.duration_s < 0:
            raise ValueError("duration_s must be >= 0")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class TelemetrySample:
    signal: str
    value: float
    unit: str
    timestamp_s: float


@dataclass(frozen=True, slots=True)
class CalibrationParameter:
    name: str
    value: float
    unit: str
    uncertainty: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must be non-empty")
        if self.uncertainty is not None and self.uncertainty < 0:
            raise ValueError("uncertainty must be >= 0")


@dataclass(frozen=True, slots=True)
class CalibrationRecord:
    device_id: str
    version: str
    parameters: tuple[CalibrationParameter, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.device_id.strip():
            raise ValueError("device_id must be non-empty")
        if not self.version.strip():
            raise ValueError("version must be non-empty")
        names = [parameter.name for parameter in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("calibration parameter names must be unique")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class ExperimentRequest:
    commands: tuple[ControlCommand, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.commands:
            raise ValueError("commands must contain at least one command")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    device_id: str
    measurements: tuple[TelemetrySample, ...]
    completed: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))
