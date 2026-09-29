# QFabric

**Hardware-agnostic control and calibration fabric for heterogeneous quantum hardware.**

> **Status:** pre-alpha / experimental. QFabric v0.1 currently provides a vendor-neutral
> software contract and deterministic reference simulator. It does **not** claim
> compatibility with physical quantum hardware unless a future adapter explicitly
> documents and tests that compatibility.

QFabric explores a thin public control layer between higher-level quantum software
and heterogeneous hardware backends. The goal is to make control commands,
capabilities, calibration records, telemetry, and experiment results explicit and
portable without forcing the core package to depend on one vendor SDK.

## Why QFabric?

Quantum hardware stacks expose different control surfaces, calibration concepts,
and telemetry formats. QFabric starts from a narrower question:

> What is the smallest useful contract that can sit above multiple hardware families
> without pretending their underlying physics is identical?

The v0.1 core therefore focuses on:

- explicit hardware capabilities;
- validated, unit-carrying control commands;
- versioned, device-scoped calibration records;
- normalized experiment requests and results;
- a strict adapter boundary for vendor- or hardware-specific implementations; and
- a deterministic simulator for contract tests.

## Architecture

```text
Applications / orchestration / digital twins
                    |
             QFabric domain API
                    |
              DeviceAdapter
        ____________|____________
       |            |            |
   Ion-trap*   Neutral-atom*   Photonic*
       |            |            |
             Physical hardware

* Future adapters. No physical-hardware compatibility is claimed in v0.1.
```

See [docs/architecture.md](docs/architecture.md) for design rules and non-goals.

## Quick start

Requires Python 3.11+.

```bash
git clone https://github.com/Takzin1/QFabric.git
cd QFabric
python -m pip install -e ".[dev]"
pytest
```

Example:

```python
from qfabric.adapters import DeterministicSimulatorAdapter
from qfabric.models import ControlCommand, ExperimentRequest

adapter = DeterministicSimulatorAdapter()

result = adapter.execute(
    ExperimentRequest(
        commands=(
            ControlCommand(
                channel="drive",
                value=1.0,
                unit="arb",
                duration_s=1e-6,
            ),
        )
    )
)

print(result.measurements)
```

The simulator validates the public contract and produces reproducible test output.
It is intentionally **not** a physics simulator.

## Core invariants

1. The core package does not import vendor SDKs.
2. Hardware-specific behavior lives behind `DeviceAdapter`.
3. Capabilities are explicit and machine-readable.
4. Calibration records are versioned and device-scoped.
5. Unsupported channels fail closed before execution.
6. Hardware compatibility claims require adapter-specific documentation and tests.

## Roadmap

### v0.1 — Contract foundation
- [x] Core domain models
- [x] Device adapter interface
- [x] Calibration boundary
- [x] Deterministic reference adapter
- [x] CI contract tests

### v0.2 — Protocol semantics
- [ ] Command envelopes and serialization
- [ ] Capability negotiation
- [ ] Calibration provenance and timestamps
- [ ] Error taxonomy
- [ ] Conformance test suite

### v0.3 — First hardware adapter
- [ ] Select one documented hardware/software interface
- [ ] Implement adapter outside the core contract
- [ ] Add reproducible integration tests
- [ ] Publish a compatibility statement with explicit limitations

## Non-goals for v0.1

QFabric v0.1 does not implement pulse compilation, optimal control, vendor
transports, hardware timing guarantees, physics-accurate simulation, or a proprietary
digital-twin/AI engine.

Keeping those concerns out of the initial core is deliberate: the public contract
should stabilize before hardware-specific complexity is added.

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
