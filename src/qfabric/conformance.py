"""Non-invasive QFabric adapter conformance checks."""

from __future__ import annotations

from dataclasses import dataclass

from qfabric.adapters.base import DeviceAdapter
from qfabric.version import SUPPORTED_PROTOCOL_VERSIONS


@dataclass(frozen=True, slots=True)
class ConformanceCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ConformanceReport:
    checks: tuple[ConformanceCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


def inspect_adapter_contract(adapter: DeviceAdapter) -> ConformanceReport:
    """Inspect metadata only; this function never sends commands to hardware."""

    capabilities = adapter.capabilities
    checks = (
        ConformanceCheck(
            "device_id.non_empty",
            bool(adapter.device_id.strip()),
            "device_id must be a non-empty string",
        ),
        ConformanceCheck(
            "protocol.compatible",
            bool(capabilities.protocol_versions & SUPPORTED_PROTOCOL_VERSIONS),
            "adapter must advertise at least one QFabric-supported protocol version",
        ),
        ConformanceCheck(
            "channels.non_empty",
            bool(capabilities.supported_channels),
            "adapter must advertise at least one supported control channel",
        ),
        ConformanceCheck(
            "channels.valid",
            all(channel.strip() for channel in capabilities.supported_channels),
            "supported channel names must be non-empty",
        ),
        ConformanceCheck(
            "calibration_keys.valid",
            all(key.strip() for key in capabilities.calibration_keys),
            "calibration key names must be non-empty",
        ),
    )
    return ConformanceReport(checks=checks)
