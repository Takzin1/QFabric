"""Stable error taxonomy for the QFabric public contract."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType
from typing import Any


class ErrorCode(str, Enum):
    INVALID_MESSAGE = "invalid_message"
    UNSUPPORTED_PROTOCOL_VERSION = "unsupported_protocol_version"
    DEVICE_MISMATCH = "device_mismatch"
    UNSUPPORTED_CHANNEL = "unsupported_channel"
    UNKNOWN_CALIBRATION_KEY = "unknown_calibration_key"
    CAPABILITY_MISMATCH = "capability_mismatch"


class QFabricError(Exception):
    """Base exception carrying a stable machine-readable error code."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = MappingProxyType(dict(details or {}))
        super().__init__(f"{code.value}: {message}")


class ProtocolError(QFabricError):
    """Wire-format or protocol-version failure."""


class ValidationError(QFabricError):
    """Domain validation failure."""


class CapabilityError(QFabricError):
    """Capability negotiation failure."""
