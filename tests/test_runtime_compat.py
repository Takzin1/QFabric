from __future__ import annotations

from datetime import UTC, datetime

from qfabric.models import ControlCommand, ExperimentRequest
from qfabric.profiles.qick import QickGeneratorBinding, QickPlanAdapter
from qfabric.protocol import CommandEnvelope
from qfabric.runtime_compat import bind_plan_calls


def _plan():
    adapter = QickPlanAdapter(
        device_id="runtime-test",
        bindings=(
            QickGeneratorBinding(logical_channel="drive", gen_ch=0, nqz=1),
        ),
    )
    envelope = CommandEnvelope(
        message_id="runtime-test-001",
        device_id=adapter.device_id,
        sent_at=datetime(2026, 9, 29, 4, 30, tzinfo=UTC),
        request=ExperimentRequest(
            commands=(
                ControlCommand(
                    channel="drive",
                    value=0.5,
                    unit="normalized_gain",
                    duration_s=1e-6,
                    metadata={
                        "qick.frequency_mhz": 100.0,
                        "qick.phase_deg": 0.0,
                        "qick.time_us": 0.0,
                    },
                ),
            )
        ),
    )
    return adapter.compile(envelope)


class CompatibleRuntime:
    def declare_gen(self, ch, nqz=1, extra=None):
        pass

    def add_pulse(self, ch, name, **kwargs):
        pass

    def pulse(self, ch, name, t=0, tag=None):
        pass


class BreakingRuntime:
    def declare_gen(self, channel, nqz=1):
        pass

    def add_pulse(self, ch, name, **kwargs):
        pass

    def pulse(self, ch, name, t=0, tag=None):
        pass


def test_runtime_binding_accepts_compatible_methods_without_invoking_them() -> None:
    checks = bind_plan_calls(
        _plan(),
        {
            "declare_gen": CompatibleRuntime.declare_gen,
            "add_pulse": CompatibleRuntime.add_pulse,
            "pulse": CompatibleRuntime.pulse,
        },
    )

    assert checks
    assert all(check.compatible for check in checks)


def test_runtime_binding_detects_breaking_signature() -> None:
    checks = bind_plan_calls(
        _plan(),
        {
            "declare_gen": BreakingRuntime.declare_gen,
            "add_pulse": BreakingRuntime.add_pulse,
            "pulse": BreakingRuntime.pulse,
        },
    )

    failures = [check for check in checks if not check.compatible]
    assert len(failures) == 1
    assert failures[0].method == "declare_gen"
    assert "rejected" in failures[0].detail


def test_runtime_binding_detects_missing_method() -> None:
    checks = bind_plan_calls(
        _plan(),
        {
            "declare_gen": CompatibleRuntime.declare_gen,
            "add_pulse": CompatibleRuntime.add_pulse,
        },
    )

    failures = [check for check in checks if not check.compatible]
    assert len(failures) == 1
    assert failures[0].method == "pulse"
    assert failures[0].detail == "runtime method is unavailable"
