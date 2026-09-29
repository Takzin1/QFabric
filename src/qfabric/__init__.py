"""QFabric public API.

QFabric is an experimental, hardware-agnostic control and calibration protocol.
It does not claim compatibility with physical quantum devices unless an adapter
explicitly documents and tests that compatibility.
"""

from .errors import (
    CapabilityError,
    ErrorCode,
    ProtocolError,
    QFabricError,
    ValidationError,
)
from .models import (
    CalibrationParameter,
    CalibrationProvenance,
    CalibrationRecord,
    ControlCommand,
    DeviceCapabilities,
    ExperimentRequest,
    ExperimentResult,
    HardwareKind,
    TelemetrySample,
)
from .protocol import (
    CapabilityNegotiationResult,
    CapabilityRequirement,
    CommandEnvelope,
    command_envelope_from_dict,
    command_envelope_to_dict,
    dumps_command_envelope,
    loads_command_envelope,
    negotiate_capabilities,
)
from .version import PACKAGE_VERSION, PROTOCOL_VERSION

__all__ = [
    "CapabilityError",
    "CapabilityNegotiationResult",
    "CapabilityRequirement",
    "CalibrationParameter",
    "CalibrationProvenance",
    "CalibrationRecord",
    "CommandEnvelope",
    "ControlCommand",
    "DeviceCapabilities",
    "ErrorCode",
    "ExperimentRequest",
    "ExperimentResult",
    "HardwareKind",
    "PACKAGE_VERSION",
    "PROTOCOL_VERSION",
    "ProtocolError",
    "QFabricError",
    "TelemetrySample",
    "ValidationError",
    "command_envelope_from_dict",
    "command_envelope_to_dict",
    "dumps_command_envelope",
    "loads_command_envelope",
    "negotiate_capabilities",
]

__version__ = PACKAGE_VERSION
