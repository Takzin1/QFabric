"""Plan-only QICK profile for QFabric.

This module deliberately does not import the QICK package and never touches hardware.
It compiles a narrow subset of QFabric commands into declarative calls matching the
public QICK tProc v2 API shape documented at a pinned upstream commit.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from qfabric.errors import ErrorCode, ValidationError
from qfabric.models import ControlCommand
from qfabric.protocol import CommandEnvelope, ensure_supported_protocol_version

QICK_REFERENCE_REPOSITORY = "openquantumhardware/qick"
QICK_REFERENCE_COMMIT = "4da51a5154e448fa3613257a967bfa6a58959a8b"
QICK_PROFILE_VERSION = "0.1.0"

_SUPPORTED_QICK_METADATA = frozenset(
    {
        "qick.frequency_mhz",
        "qick.phase_deg",
        "qick.time_us",
        "qick.style",
    }
)


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


def _require_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(
            ErrorCode.INVALID_MESSAGE,
            f"{field_name} must be numeric",
            details={"field": field_name},
        )
    return float(value)


@dataclass(frozen=True, slots=True)
class QickGeneratorBinding:
    """Bind one logical QFabric channel to one QICK generator channel."""

    logical_channel: str
    gen_ch: int
    nqz: int = 1

    def __post_init__(self) -> None:
        if not self.logical_channel.strip():
            raise ValueError("logical_channel must be non-empty")
        if self.gen_ch < 0:
            raise ValueError("gen_ch must be >= 0")
        if self.nqz <= 0:
            raise ValueError("nqz must be > 0")


@dataclass(frozen=True, slots=True)
class QickCall:
    """One declarative QICK program method call."""

    method: str
    kwargs: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.method not in {"declare_gen", "add_pulse", "pulse"}:
            raise ValueError(f"unsupported QICK method {self.method!r}")
        object.__setattr__(self, "kwargs", _freeze_mapping(self.kwargs))


@dataclass(frozen=True, slots=True)
class QickExecutionPlan:
    """A hardware-free plan that can be reviewed before QICK execution."""

    device_id: str
    message_id: str
    profile_version: str
    qick_reference_repository: str
    qick_reference_commit: str
    calls: tuple[QickCall, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "message_id": self.message_id,
            "profile_version": self.profile_version,
            "qick_reference_repository": self.qick_reference_repository,
            "qick_reference_commit": self.qick_reference_commit,
            "calls": [
                {"method": call.method, "kwargs": dict(call.kwargs)}
                for call in self.calls
            ],
        }


class QickPlanAdapter:
    """Compile QFabric command envelopes into a narrow QICK tProc v2 call plan.

    Supported v0.1 profile:
    - QICK `const` pulses only
    - QFabric command unit must be `normalized_gain`
    - command.value maps to QICK gain and must be within [-1, 1]
    - command.duration_s maps to QICK pulse length in microseconds
    - metadata must provide frequency and schedule time in QICK units

    The adapter never imports QICK and never executes or acquires from hardware.
    """

    def __init__(
        self,
        *,
        device_id: str,
        bindings: tuple[QickGeneratorBinding, ...],
    ) -> None:
        if not device_id.strip():
            raise ValueError("device_id must be non-empty")
        if not bindings:
            raise ValueError("bindings must contain at least one generator binding")

        logical_channels = [binding.logical_channel for binding in bindings]
        if len(logical_channels) != len(set(logical_channels)):
            raise ValueError("logical channel bindings must be unique")

        generator_channels = [binding.gen_ch for binding in bindings]
        if len(generator_channels) != len(set(generator_channels)):
            raise ValueError("QICK generator channel bindings must be unique")

        self._device_id = device_id
        self._bindings = {
            binding.logical_channel: binding
            for binding in bindings
        }

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def bound_channels(self) -> frozenset[str]:
        return frozenset(self._bindings)

    def compile(self, envelope: CommandEnvelope) -> QickExecutionPlan:
        ensure_supported_protocol_version(envelope.protocol_version)
        if envelope.device_id != self.device_id:
            raise ValidationError(
                ErrorCode.DEVICE_MISMATCH,
                "QICK plan target does not match adapter device",
                details={
                    "target": envelope.device_id,
                    "adapter_device_id": self.device_id,
                },
            )

        calls: list[QickCall] = []
        used_generators: set[int] = set()

        for index, command in enumerate(envelope.request.commands):
            binding = self._binding_for(command)
            if binding.gen_ch not in used_generators:
                calls.append(
                    QickCall(
                        method="declare_gen",
                        kwargs={"ch": binding.gen_ch, "nqz": binding.nqz},
                    )
                )
                used_generators.add(binding.gen_ch)

            pulse_name = f"qf_{index:04d}"
            pulse_kwargs = self._compile_const_pulse(
                command=command,
                binding=binding,
                pulse_name=pulse_name,
            )
            calls.append(QickCall(method="add_pulse", kwargs=pulse_kwargs))
            calls.append(
                QickCall(
                    method="pulse",
                    kwargs={
                        "ch": binding.gen_ch,
                        "name": pulse_name,
                        "t": _require_number(
                            command.metadata.get("qick.time_us"),
                            "qick.time_us",
                        ),
                    },
                )
            )

        return QickExecutionPlan(
            device_id=envelope.device_id,
            message_id=envelope.message_id,
            profile_version=QICK_PROFILE_VERSION,
            qick_reference_repository=QICK_REFERENCE_REPOSITORY,
            qick_reference_commit=QICK_REFERENCE_COMMIT,
            calls=tuple(calls),
        )

    def _binding_for(self, command: ControlCommand) -> QickGeneratorBinding:
        binding = self._bindings.get(command.channel)
        if binding is None:
            raise ValidationError(
                ErrorCode.CAPABILITY_MISMATCH,
                f"No QICK generator binding for channel {command.channel!r}",
                details={
                    "channel": command.channel,
                    "bound_channels": sorted(self._bindings),
                },
            )
        return binding

    def _compile_const_pulse(
        self,
        *,
        command: ControlCommand,
        binding: QickGeneratorBinding,
        pulse_name: str,
    ) -> dict[str, Any]:
        if command.unit != "normalized_gain":
            raise ValidationError(
                ErrorCode.CAPABILITY_MISMATCH,
                "QICK profile v0.1 requires unit='normalized_gain'",
                details={"received_unit": command.unit},
            )
        if not -1.0 <= command.value <= 1.0:
            raise ValidationError(
                ErrorCode.INVALID_MESSAGE,
                "normalized_gain must be within [-1, 1]",
                details={"gain": command.value},
            )
        if command.duration_s is None or command.duration_s <= 0:
            raise ValidationError(
                ErrorCode.INVALID_MESSAGE,
                "QICK const pulse requires duration_s > 0",
            )

        style = command.metadata.get("qick.style", "const")
        if style != "const":
            raise ValidationError(
                ErrorCode.CAPABILITY_MISMATCH,
                "QICK profile v0.1 supports style='const' only",
                details={"received_style": style},
            )

        qick_keys = {
            key
            for key in command.metadata
            if key.startswith("qick.")
        }
        unknown_qick_keys = qick_keys - _SUPPORTED_QICK_METADATA
        if unknown_qick_keys:
            raise ValidationError(
                ErrorCode.INVALID_MESSAGE,
                "Unknown QICK metadata field(s)",
                details={"unknown_fields": sorted(unknown_qick_keys)},
            )

        frequency_mhz = _require_number(
            command.metadata.get("qick.frequency_mhz"),
            "qick.frequency_mhz",
        )
        phase_deg = _require_number(
            command.metadata.get("qick.phase_deg", 0.0),
            "qick.phase_deg",
        )
        time_us = _require_number(
            command.metadata.get("qick.time_us"),
            "qick.time_us",
        )

        if frequency_mhz < 0:
            raise ValidationError(
                ErrorCode.INVALID_MESSAGE,
                "qick.frequency_mhz must be >= 0",
            )
        if time_us < 0:
            raise ValidationError(
                ErrorCode.INVALID_MESSAGE,
                "qick.time_us must be >= 0",
            )

        return {
            "ch": binding.gen_ch,
            "name": pulse_name,
            "style": "const",
            "freq": frequency_mhz,
            "phase": phase_deg,
            "gain": float(command.value),
            "length": command.duration_s * 1_000_000.0,
        }
