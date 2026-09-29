# QFabric

**Hardware-agnostic control and calibration fabric for heterogeneous quantum hardware.**

> **Status:** pre-alpha / experimental. QFabric v0.2 defines a vendor-neutral,
> versioned software protocol plus a deterministic reference simulator. It does
> **not** claim compatibility with physical quantum hardware unless an adapter
> explicitly documents and tests that compatibility.

QFabric explores a thin public control layer between higher-level quantum software
and heterogeneous hardware backends. The public core makes protocol versions,
control commands, capabilities, calibration provenance, telemetry, and failure modes
explicit without depending on one vendor SDK.

## Why QFabric?

Quantum hardware stacks expose different control surfaces, calibration concepts,
and telemetry formats. QFabric asks:

> What is the smallest useful protocol that can sit above multiple hardware families
> without pretending their underlying physics is identical?

v0.2 focuses on:

- versioned command envelopes;
- deterministic JSON serialization;
- capability negotiation before execution;
- timestamped, attributable calibration records;
- stable machine-readable error codes;
- a strict vendor-neutral adapter boundary; and
- non-invasive conformance inspection.

## Architecture

~~~text
Applications / orchestration / digital twins
                    |
            QFabric Protocol v0.2
       envelopes / negotiation / errors
                    |
              DeviceAdapter
        ____________|____________
       |            |            |
   Ion-trap*   Neutral-atom*   Photonic*
       |            |            |
             Physical hardware

* Future adapters. No physical-hardware compatibility is claimed in v0.2.
~~~

See [docs/architecture.md](docs/architecture.md) and
[docs/protocol.md](docs/protocol.md).

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

Example:

~~~python
from datetime import datetime, timezone

from qfabric.adapters import DeterministicSimulatorAdapter
from qfabric.models import ControlCommand, ExperimentRequest
from qfabric.protocol import CommandEnvelope, dumps_command_envelope

adapter = DeterministicSimulatorAdapter()

envelope = CommandEnvelope(
    message_id="msg-001",
    device_id=adapter.device_id,
    sent_at=datetime.now(timezone.utc),
    request=ExperimentRequest(
        commands=(
            ControlCommand(
                channel="drive",
                value=1.0,
                unit="arb",
                duration_s=1e-6,
            ),
        )
    ),
)

print(dumps_command_envelope(envelope))
result = adapter.execute_envelope(envelope)
print(result.measurements)
~~~

The deterministic simulator validates the public contract and produces reproducible
test output. It is intentionally **not** a physics simulator.

## Core invariants

1. The core package does not import vendor SDKs.
2. Hardware-specific behavior lives behind `DeviceAdapter`.
3. Cross-boundary commands carry an explicit protocol version and target device.
4. Capabilities are negotiated explicitly rather than silently degraded.
5. Calibration records are versioned, timestamped, and carry provenance.
6. Unsupported channels and device mismatches fail closed with stable error codes.
7. Generic conformance inspection never executes hardware commands.
8. Hardware compatibility claims require adapter-specific documentation and tests.

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

### v0.3 — First documented adapter
- [ ] Select one public hardware/software interface
- [ ] Implement the adapter outside the generic core
- [ ] Add reproducible integration tests
- [ ] Publish an explicit compatibility statement and limitations
- [ ] Add a result/telemetry wire envelope only where real integration requires it

## Open-core boundary

QFabric publishes the reusable protocol, SDK boundary, schemas, and adapter contract.

Physics-accurate digital twins, proprietary inference engines, private training data,
and commercial evaluation services are intentionally outside this repository.

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
