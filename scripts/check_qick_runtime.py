"""Validate a QFabric QICK plan against an installed pinned QICK runtime."""

from __future__ import annotations

import sys
from datetime import UTC, datetime

from qfabric.models import ControlCommand, ExperimentRequest
from qfabric.profiles.qick import QickGeneratorBinding, QickPlanAdapter
from qfabric.protocol import CommandEnvelope
from qfabric.runtime_compat import format_runtime_report, inspect_installed_qick_runtime


def _fixture_plan():
    adapter = QickPlanAdapter(
        device_id="qick-runtime-fixture",
        bindings=(
            QickGeneratorBinding(logical_channel="drive", gen_ch=0, nqz=1),
        ),
    )
    envelope = CommandEnvelope(
        message_id="runtime-fixture-001",
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


def main() -> int:
    report = inspect_installed_qick_runtime(_fixture_plan())
    print(format_runtime_report(report))
    return 0 if report.compatible else 1


if __name__ == "__main__":
    sys.exit(main())
