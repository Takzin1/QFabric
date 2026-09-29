# QFabric Protocol v0.2

QFabric v0.2 defines a versioned, transport-neutral contract between client software
and a hardware adapter. The protocol is intentionally narrower than a vendor SDK: it
defines message shape, capability negotiation, calibration traceability, and stable
failure codes while leaving transport and hardware physics behind the adapter boundary.

## Versioning

The current protocol version is `0.2.0`.

Every command envelope MUST carry `protocol_version`. Receivers MUST reject versions
they do not explicitly support with `unsupported_protocol_version`.

Protocol versions use semantic `MAJOR.MINOR.PATCH` notation. This repository currently
advertises exactly one supported protocol version.

## Command envelope

A command crossing the adapter boundary has six required top-level fields:

- `message_type`: currently `"command"`
- `protocol_version`: protocol contract version
- `message_id`: caller-supplied message identifier
- `device_id`: explicit target device
- `sent_at`: timezone-aware ISO-8601 timestamp
- `request`: one or more validated control commands plus optional metadata

Example:

~~~json
{
  "device_id": "sim-001",
  "message_id": "msg-001",
  "message_type": "command",
  "protocol_version": "0.2.0",
  "request": {
    "commands": [
      {
        "channel": "drive",
        "duration_s": 0.000001,
        "metadata": {"phase": 0.25},
        "unit": "arb",
        "value": 0.75
      }
    ],
    "metadata": {"purpose": "example"}
  },
  "sent_at": "2026-09-29T04:05:00Z"
}
~~~

The canonical JSON encoder sorts keys, rejects NaN/Infinity, and emits UTC timestamps.
The decoder rejects unknown top-level envelope fields to prevent silent protocol drift.

See `spec/qfabric-command-envelope.schema.json` for the language-neutral schema.

## Capability negotiation

Clients declare minimum requirements through `CapabilityRequirement`:

- required control channels
- required calibration keys
- accepted protocol versions
- whether closed-loop feedback is required

An adapter returns `CapabilityNegotiationResult` rather than silently degrading a
request. A result is compatible only when a protocol version overlaps and all required
capabilities are present.

## Calibration provenance

A v0.2 `CalibrationRecord` is:

- device-scoped
- versioned
- timestamped with a timezone-aware `created_at`
- linked to a `CalibrationProvenance` record

Provenance captures at minimum a source and method, with optional actor, evidence URI,
and parent calibration version.

QFabric does not define the scientific validity of a calibration. It defines the
traceability fields required to carry one across the public contract.

## Stable error taxonomy

Public boundary failures expose a machine-readable `ErrorCode`:

| Code | Meaning |
| --- | --- |
| `invalid_message` | malformed or ambiguous protocol message |
| `unsupported_protocol_version` | no supported version match |
| `device_mismatch` | message/calibration targets another device |
| `unsupported_channel` | command names a channel the adapter did not advertise |
| `unknown_calibration_key` | calibration uses an unadvertised key |
| `capability_mismatch` | reserved for capability-level failures |

Human-readable text may evolve. Clients SHOULD branch on the error code, not message text.

## Conformance

`inspect_adapter_contract()` is deliberately non-invasive. It inspects identity and
advertised capabilities only and never calls `execute()` or sends a control command.

Behavioral execution tests in this repository use only the deterministic simulator.
A future physical-hardware adapter must define its own safe integration procedure and
document any assumptions before claiming QFabric compatibility.

## Non-goals

Protocol v0.2 does not standardize:

- pulse compilation or optimal-control algorithms
- vendor transports
- hardware timing guarantees
- physics-accurate simulation
- proprietary digital-twin or inference engines
- compatibility with any particular commercial or research device
