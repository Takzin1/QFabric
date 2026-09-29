"""Controlled runtime compatibility checks for the QICK planning profile.

This module may import an installed QICK package, but it never instantiates QICK
programs, connects to an RFSoC, or executes a pulse. Runtime compatibility here means
that QFabric-generated keyword calls can be bound to the installed QICK method
signatures.
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from qfabric.profiles.qick import (
    QICK_REFERENCE_COMMIT,
    QickExecutionPlan,
)

QICK_REFERENCE_VERSION = "0.2.432"


@dataclass(frozen=True, slots=True)
class RuntimeCallCheck:
    method: str
    compatible: bool
    detail: str
    kwargs: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kwargs", MappingProxyType(dict(self.kwargs)))


@dataclass(frozen=True, slots=True)
class QickRuntimeReport:
    installed_version: str | None
    expected_version: str
    reference_commit: str
    import_compatible: bool
    version_compatible: bool
    calls: tuple[RuntimeCallCheck, ...]

    @property
    def compatible(self) -> bool:
        return (
            self.import_compatible
            and self.version_compatible
            and all(call.compatible for call in self.calls)
        )


def bind_plan_calls(
    plan: QickExecutionPlan,
    methods: Mapping[str, Callable[..., Any]],
) -> tuple[RuntimeCallCheck, ...]:
    """Bind plan kwargs to unbound backend methods without invoking those methods."""

    checks: list[RuntimeCallCheck] = []
    for call in plan.calls:
        method = methods.get(call.method)
        if method is None:
            checks.append(
                RuntimeCallCheck(
                    method=call.method,
                    compatible=False,
                    detail="runtime method is unavailable",
                    kwargs=call.kwargs,
                )
            )
            continue

        signature = inspect.signature(method)
        try:
            signature.bind(None, **dict(call.kwargs))
        except TypeError as exc:
            checks.append(
                RuntimeCallCheck(
                    method=call.method,
                    compatible=False,
                    detail=f"runtime signature rejected QFabric call: {exc}",
                    kwargs=call.kwargs,
                )
            )
            continue

        checks.append(
            RuntimeCallCheck(
                method=call.method,
                compatible=True,
                detail="runtime signature accepts QFabric call",
                kwargs=call.kwargs,
            )
        )

    return tuple(checks)


def inspect_installed_qick_runtime(
    plan: QickExecutionPlan,
    *,
    expected_version: str = QICK_REFERENCE_VERSION,
) -> QickRuntimeReport:
    """Import QICK and verify plan-call signature compatibility without execution."""

    try:
        qick = importlib.import_module("qick")
        qick_asm = importlib.import_module("qick.qick_asm")
        asm_v2 = importlib.import_module("qick.asm_v2")
    except (ImportError, RuntimeError, OSError) as exc:
        return QickRuntimeReport(
            installed_version=None,
            expected_version=expected_version,
            reference_commit=QICK_REFERENCE_COMMIT,
            import_compatible=False,
            version_compatible=False,
            calls=(
                RuntimeCallCheck(
                    method="<import>",
                    compatible=False,
                    detail=f"QICK runtime import failed: {exc}",
                    kwargs={},
                ),
            ),
        )

    installed_version = str(getattr(qick, "__version__", ""))
    version_compatible = installed_version == expected_version

    methods: dict[str, Callable[..., Any]] = {
        "declare_gen": qick_asm.AbsQickProgram.declare_gen,
        "add_pulse": asm_v2.QickProgramV2.add_pulse,
        "pulse": asm_v2.AsmV2.pulse,
    }
    calls = bind_plan_calls(plan, methods)

    return QickRuntimeReport(
        installed_version=installed_version,
        expected_version=expected_version,
        reference_commit=QICK_REFERENCE_COMMIT,
        import_compatible=True,
        version_compatible=version_compatible,
        calls=calls,
    )


def format_runtime_report(report: QickRuntimeReport) -> str:
    lines = [
        f"reference_commit={report.reference_commit}",
        f"expected_version={report.expected_version}",
        f"installed_version={report.installed_version}",
        f"import_compatible={str(report.import_compatible).lower()}",
        f"version_compatible={str(report.version_compatible).lower()}",
        f"compatible={str(report.compatible).lower()}",
    ]
    for check in report.calls:
        status = "PASS" if check.compatible else "FAIL"
        lines.append(f"{status} {check.method} - {check.detail}")
    return "\n".join(lines)
