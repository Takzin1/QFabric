"""QFabric public API.

QFabric is an experimental, hardware-agnostic control and calibration abstraction.
It does not claim compatibility with physical quantum devices unless an adapter
explicitly documents and tests that compatibility.
"""

from .models import (
    CalibrationParameter,
    CalibrationRecord,
    ControlCommand,
    DeviceCapabilities,
    ExperimentRequest,
    ExperimentResult,
    HardwareKind,
    TelemetrySample,
)

__all__ = [
    "CalibrationParameter",
    "CalibrationRecord",
    "ControlCommand",
    "DeviceCapabilities",
    "ExperimentRequest",
    "ExperimentResult",
    "HardwareKind",
    "TelemetrySample",
]

__version__ = "0.1.0"
