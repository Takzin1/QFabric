"""Hardware-free QICK-specific readout intent and conservative preflight.

This module does NOT compile a `declare_readout`, `trigger`, or `acquire`
call. No QICK import, program construction, hardware I/O or measurements occur.

All fields refer to a hypothetical board configuration and must not be used as
claims about a real ADC, calibration state or frequency/timing capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from qfabric.errors import ErrorCode, ValidationError
from qfabric.profiles.qick import QICK_REFERENCE_COMMIT, QICK_REFERENCE_REPOSITORY

MAX_READOUT_SHOTS = 2_000_000
MAX_CAPTURE_US = 1_000_000.0
MAX_READOUT_CHANNELS = 16


def _integer(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(
            ErrorCode.INVALID_MESSAGE,
            f"{field} must be an integer",
            details={"field": field},
        )
    if not minimum <= value <= maximum:
        raise ValidationError(
            ErrorCode.INVALID_MESSAGE,
            f"{field} outside supported software bounds",
            details={"field": field},
        )
    return value


def _number(value: Any, field: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(
            ErrorCode.INVALID_MESSAGE,
            f"{field} must be numeric",
            details={"field": field},
        )
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValidationError(
            ErrorCode.INVALID_MESSAGE,
            f"{field} must be finite",
            details={"field": field},
        ) from exc
    if not isfinite(number) or not minimum <= number <= maximum:
        raise ValidationError(
            ErrorCode.INVALID_MESSAGE,
            f"{field} outside finite software bounds",
            details={"field": field},
        )
    return number


@dataclass(frozen=True, slots=True)
class QickReadoutIntent:
    """A proposed readout configuration; never an executable QICK command."""

    device_id: str
    readout_gen_ch: int
    adc_channels: tuple[int, ...]
    frequency_mhz: float
    capture_length_us: float
    trigger_offset_us: float
    shots: int
    calibration_ref: str = "unverified"

    def __post_init__(self) -> None:
        if not isinstance(self.device_id, str) or not self.device_id.strip():
            raise ValidationError(ErrorCode.INVALID_MESSAGE, "device_id must be non-empty")
        _integer(self.readout_gen_ch, "readout_gen_ch", 0, 65535)
        if not isinstance(self.adc_channels, tuple) or not (
            1 <= len(self.adc_channels) <= MAX_READOUT_CHANNELS
        ):
            raise ValidationError(
                ErrorCode.INVALID_MESSAGE, "adc_channels must be a nonempty bounded tuple"
            )
        for channel in self.adc_channels:
            _integer(channel, "adc_channels", 0, 65535)
        if len(set(self.adc_channels)) != len(self.adc_channels):
            raise ValidationError(ErrorCode.INVALID_MESSAGE, "adc_channels must be unique")
        _number(self.frequency_mhz, "frequency_mhz", 0.0, 1_000_000.0)
        _number(self.capture_length_us, "capture_length_us", 0.0, MAX_CAPTURE_US)
        if self.capture_length_us == 0:
            raise ValidationError(ErrorCode.INVALID_MESSAGE, "capture_length_us must be positive")
        _number(self.trigger_offset_us, "trigger_offset_us", 0.0, MAX_CAPTURE_US)
        _integer(self.shots, "shots", 1, MAX_READOUT_SHOTS)
        if not isinstance(self.calibration_ref, str) or not (
            1 <= len(self.calibration_ref.strip()) <= 128
        ):
            raise ValidationError(
                ErrorCode.INVALID_MESSAGE, "calibration_ref must be a bounded label"
            )


@dataclass(frozen=True, slots=True)
class QickReadoutPlan:
    """Immutable, serializable readout *intent*, not a hardware execution plan."""

    intent: QickReadoutIntent

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "qick_readout_proposal",
            "status": "intent_only",
            "device_id": self.intent.device_id,
            "readout_gen_ch": self.intent.readout_gen_ch,
            "adc_channels": list(self.intent.adc_channels),
            "frequency_mhz": float(self.intent.frequency_mhz),
            "capture_length_us": float(self.intent.capture_length_us),
            "trigger_offset_us": float(self.intent.trigger_offset_us),
            "shots": self.intent.shots,
            "calibration_ref": self.intent.calibration_ref,
            "qick_reference_repository": QICK_REFERENCE_REPOSITORY,
            "qick_reference_commit": QICK_REFERENCE_COMMIT,
            "hardwareExecuted": False,
            "provenance": "synthetic_intent",
            "note": (
                "No declare_readout / trigger / acquire calls are compiled "
                "or executed; software bounds do not validate a board."
            ),
        }


class QickReadoutPlanner:
    """Validate explicit resource allowlists and build a non-executing intent."""

    def __init__(
        self,
        *,
        device_id: str,
        generator_channels: tuple[int, ...],
        adc_channels: tuple[int, ...],
    ) -> None:
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("device_id must be non-empty")
        if not generator_channels or not adc_channels:
            raise ValueError("resource allowlists must be non-empty")
        for channel in (*generator_channels, *adc_channels):
            _integer(channel, "allowed_channel", 0, 65535)
        if len(set(generator_channels)) != len(generator_channels):
            raise ValueError("generator_channels must be unique")
        if len(set(adc_channels)) != len(adc_channels):
            raise ValueError("adc_channels must be unique")
        self._device_id = device_id
        self._generators = frozenset(generator_channels)
        self._adcs = frozenset(adc_channels)

    def plan(self, intent: QickReadoutIntent) -> QickReadoutPlan:
        if intent.device_id != self._device_id:
            raise ValidationError(
                ErrorCode.DEVICE_MISMATCH,
                "Readout intent targets a different logical device",
                details={"expected": self._device_id, "received": intent.device_id},
            )
        if intent.readout_gen_ch not in self._generators:
            raise ValidationError(
                ErrorCode.CAPABILITY_MISMATCH,
                "No declared generator binding for readout intent",
                details={"readout_gen_ch": intent.readout_gen_ch},
            )
        unknown_adcs = set(intent.adc_channels) - self._adcs
        if unknown_adcs:
            raise ValidationError(
                ErrorCode.CAPABILITY_MISMATCH,
                "Readout intent references unbound ADC channels",
                details={"adc_channels": sorted(unknown_adcs)},
            )
        return QickReadoutPlan(intent=intent)
