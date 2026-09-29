# QFabric

**Hardware-agnostic control and calibration fabric for heterogeneous quantum hardware.**

> **Status:** pre-alpha / experimental. QFabric v0.3 defines a vendor-neutral,
> versioned control protocol and introduces a pinned, plan-only QICK backend profile.
> It does **not** claim physical-hardware compatibility unless a future executor and
> hardware-specific integration are explicitly tested.

QFabric explores a thin public control layer between higher-level quantum software
and heterogeneous hardware backends. The public core makes protocol versions,
control commands, capabilities, calibration provenance, backend mappings, and failure
modes explicit without coupling the core package to one vendor SDK.

## Why QFabric?

Quantum hardware stacks expose different control surfaces, calibration concepts,
and telemetry formats. QFabric asks:

> What is the smallest useful protocol that can sit above multiple hardware families
> without pretending their underlying physics is identical?

v0.3 adds one more question:

> Can that protocol be mapped deterministically onto a real, public quantum-control
> API without silently importing its runtime or pretending hardware was exercised?

The first answer is the **QICK plan profile**, pinned to upstream commit
`4da51a5154e448fa3613257a967bfa6a58959a8b`.

## Architecture

~~~text
Applications / orchestration / digital twins
                    |
            QFabric Protocol v0.2
       envelopes / negotiation / errors
                    |
             QFabric domain API
                    |
       +------------+-------------+
       |                          |
 deterministic sim          QICK plan profile
                                   |
                         declare_gen / add_pulse /
                               pulse call plan
                                   |
                         no hardware I/O here
~~~

See [docs/architecture.md](docs/architecture.md),
[docs/protocol.md](docs/protocol.md), and
[docs/adapters/qick-plan.md](docs/adapters/qick-plan.md).

The language-neutral command schema lives at
[spec/qfabric-command-envelope.schema.json](spec/qfabric-command-envelope.schema.json).

## Quick start

Requires Python 3.11+.

~~~bash
git clone https://github.com/Takzin1/QFabric.git
cd QFabric
python -m pip install -e ".[dev]"
pytest
~~~

### QICK plan example

~~~python
from datetime import UTC, datetime

from qfabric.models import ControlCommand, ExperimentRequest
from qfabric.profiles.qick import QickGeneratorBinding, QickPlanAdapter
from qfabric.protocol import CommandEnvelope

adapter = QickPlanAdapter(
    device_id="qick-lab-01",
    bindings=(
        QickGeneratorBinding(logical_channel="drive", gen_ch=0, nqz=1),
    ),
)

envelope = CommandEnvelope(
    message_id="msg-001",
    device_id="qick-lab-01",
    sent_at=datetime.now(UTC),
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

plan = adapter.compile(envelope)

for call in plan.calls:
    print(call.method, dict(call.kwargs))
~~~

This produces a reviewable QICK-shaped plan. It does **not** dispatch the plan to a
QICK program or RFSoC.

## Core invariants

1. The core package does not import vendor SDKs.
2. Hardware-specific behavior lives behind explicit adapter/profile boundaries.
3. Cross-boundary commands carry an explicit protocol version and target device.
4. Capabilities are negotiated explicitly rather than silently degraded.
5. Calibration records are versioned, timestamped, and carry provenance.
6. Unsupported channels and device mismatches fail closed with stable error codes.
7. Generic conformance inspection never executes hardware commands.
8. Backend profiles pin the upstream source they were verified against.
9. Plan generation and physical execution remain separate.
10. Hardware compatibility claims require hardware-specific documentation and tests.

## Roadmap

### v0.1 — Contract foundation
- [x] Core domain models
- [x] Device adapter interface
- [x] Calibration boundary
- [x] Deterministic reference adapter
- [x] CI contract tests

### v0.2 — Protocol semantics
- [x] Command envelopes and deterministic serialization
- [x] Protocol versioning
- [x] Capability negotiation
- [x] Calibration provenance and timestamps
- [x] Stable error taxonomy
- [x] Non-invasive conformance inspection
- [x] Language-neutral JSON Schema

### v0.3 — First documented backend profile
- [x] Select a public control interface: QICK
- [x] Pin the upstream reference commit
- [x] Map QFabric const pulses to `declare_gen / add_pulse / pulse`
- [x] Keep plan generation independent of the QICK runtime
- [x] Add deterministic profile tests
- [x] Publish explicit compatibility limits
- [ ] Validate against a controlled QICK software fixture or hardware environment

### Next
- [ ] Add fixture-based QICK drift detection against a pinned release
- [ ] Decide whether readout deserves a generic QFabric primitive or stays profile-specific
- [ ] Add result/telemetry wire envelopes only when a real integration requires them
- [ ] Evaluate a second backend profile to pressure-test the abstraction

## Open-core boundary

QFabric publishes the reusable protocol, SDK boundary, schemas, planning profiles,
and adapter contract.

Physics-accurate digital twins, proprietary inference engines, private training data,
and commercial evaluation services are intentionally outside this repository.

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
