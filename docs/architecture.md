# QFabric architecture

## Goal

QFabric defines a small, vendor-neutral contract between higher-level quantum
applications and concrete hardware-control backends.

It separates four concerns:

1. **Domain model** — commands, calibration records, capabilities, telemetry,
   requests, and results.
2. **Adapter contract** — the interface every physical or simulated backend must implement.
3. **Calibration boundary** — versioned, device-scoped parameters validated against capabilities.
4. **Execution boundary** — validated requests enter an adapter; normalized results leave it.

## Layering

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

## Design rules

- The core package MUST NOT import a vendor SDK.
- Hardware-specific concepts belong behind an adapter.
- Capabilities MUST be explicit and machine-readable.
- Calibration records MUST be device-scoped and versioned.
- Unknown control channels MUST fail closed before adapter execution.
- The deterministic simulator MUST remain physics-agnostic; it exists for contract testing.

## v0.1 non-goals

- Pulse compilation or optimal-control algorithms.
- Vendor-specific transports.
- Hardware timing guarantees.
- Physics-accurate simulation.
- Claims of compatibility with any commercial or research quantum device.
- Digital-twin or proprietary inference engines.

These exclusions are deliberate: QFabric first stabilizes the public control
contract, then adds adapters only where their semantics can be documented and tested.
