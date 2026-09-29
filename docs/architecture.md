# QFabric architecture

## Goal

QFabric defines a small, vendor-neutral protocol between higher-level quantum
applications and concrete hardware-control backends.

v0.3 separates six concerns:

1. **Domain model** — commands, calibration records, capabilities, telemetry,
   requests, and results.
2. **Protocol layer** — versioned envelopes, deterministic JSON serialization,
   capability negotiation, and stable error codes.
3. **Adapter contract** — the interface each physical or simulated backend implements.
4. **Planning profiles** — pinned, backend-specific translation into reviewable
   execution plans without hardware I/O.
5. **Calibration boundary** — versioned, device-scoped parameters with timestamped provenance.
6. **Conformance boundary** — non-invasive inspection of an adapter's declared contract.

## Layering

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
  DeviceAdapter              Planning Profile
       |                          |
 deterministic sim          QICK plan profile
                                  |
                        reviewed call plan only
                                  |
                     explicit future executor
                                  |
                         QICK / physical RFSoC
~~~

The QICK profile is intentionally plan-only. It emits a deterministic representation
of the documented QICK tProc v2 call sequence but does not import QICK or perform
hardware I/O.

The protocol remains transport-neutral. QFabric does not require HTTP, gRPC, sockets,
or any vendor transport in the core package.

## Design rules

- The core package MUST NOT import a vendor SDK.
- Hardware-specific concepts belong behind an adapter or planning profile.
- Backend planning profiles MUST pin the upstream implementation or documentation
  reference they were verified against.
- Planning and physical execution MUST remain separate boundaries.
- Every cross-boundary command MUST be protocol-versioned.
- Capabilities MUST be explicit and machine-readable.
- Clients MUST be able to detect capability mismatches before execution.
- Calibration records MUST be device-scoped, versioned, timestamped, and attributable.
- Unknown control channels MUST fail closed before adapter execution or plan generation.
- Public failures MUST carry stable machine-readable error codes.
- Generic conformance inspection MUST NOT send commands to physical hardware.
- The deterministic simulator MUST remain physics-agnostic; it exists for contract testing.

## Open-core boundary

The public repository contains the reusable control contract, protocol schema,
adapter interface, planning profiles, and conformance machinery.

Physics-accurate simulation, proprietary digital-twin models, private datasets,
and proprietary inference logic are intentionally outside QFabric's public core.

## v0.3 non-goals

- Direct QICK hardware execution.
- Pulse compilation or optimal-control algorithms beyond explicitly documented
  backend mapping rules.
- Vendor-specific network transports.
- Hardware timing guarantees.
- Physics-accurate simulation.
- Claims of compatibility with any commercial or research quantum device.
- Digital-twin or proprietary inference engines.

See [protocol.md](protocol.md) for normative protocol behavior and
[adapters/qick-plan.md](adapters/qick-plan.md) for the first pinned backend profile.
