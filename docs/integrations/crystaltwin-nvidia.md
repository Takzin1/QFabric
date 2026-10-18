# QFabric × CrystalTwinAI × NVIDIA: research bridge v1

**Maturity:** offline research demonstrator; not hardware-control software.
**Repos:** [QFabric](https://github.com/Takzin1/QFabric) (Apache-2.0) and
[CrystalTwinAI](https://github.com/Takzin1/crystaltwinai) (MIT).
This document proposes a hackathon submission architecture; no eligibility,
prize criteria, deadline, or mandatory NVIDIA service is asserted. Verify the
specific Devpost challenge rules separately before submission.

## Problem / thesis

Experimental research prototypes typically lose provenance between simulation,
instrument control planning, and accelerated numeric processing. This project
demonstrates an *auditable interoperability boundary*, not quantum superiority:
a versioned synthetic crystallization snapshot, QICK-shaped **plan-only**
control metadata, and reproducible synthetic IQ analytics are linked into
one report. CrystalTwinAI can display the report without making a network request.

## v1 dataflow (implemented)

```text
CrystalTwinAI Next.js (existing educational crystallization engine)
     |  locally download snapshot JSON (synthetic + schemaVersion)
     v
QFabric Python bridge CLI (validate, SHA-256, plan-only QICK)
     |                   |
     |                   +--> analytic synthetic IQ batch
     |                        CPU fallback OR actual CuPy/CUDA GPU
     v
versioned report JSON with provenance, immutable input fingerprint,
readout intent (never executed), QICK call plan and backend label
     |
     v
CrystalTwinAI report-import panel (client-side validation + display)
```

Run after installing QFabric in editable mode:

```bash
python -m pip install -e ".[dev]"
python scripts/crystaltwin_bridge.py snapshot.json report.json --backend cpu --shots 4096
# CUDA only on an NVIDIA CUDA machine with compatible CuPy installed:
python scripts/crystaltwin_bridge.py snapshot.json gpu-report.json --backend cuda --shots 1000000
```

`--backend auto` attempts CUDA and **explicitly** falls back to CPU; the output
always records the backend that actually performed the work. Do not describe
a CPU report as GPU-accelerated. CUDA hardware is not exercised in CI.

## Interface contracts

Snapshot schema identifier: `crystaltwin-qfabric-snapshot/1`.

Required fields: `schemaVersion`, `kind="educational_snapshot"`,
`source`, `input`, `summary`, `trajectory`.
The source must explicitly be `Takzin1/crystaltwinai`,
`synthetic` and `educational_simulation`; all reported numbers must be
finite; trajectory steps must be monotonically increasing. Raw input size
is bounded to 512 KiB; `timeSteps` must match the number of rows (max 200).

Report identifier: `qfabric-crystaltwin-report/1`.
Required sections:
- `source.sha256`: digest of **exact input bytes** (not proof of authenticity);
- `snapshot`: input values, educational summary, row count;
- `qfabric`: pinned control plan and an **intent-only** readout;
- `analytics`: synthetic IQ means / power / backend / wall time;
- `disclaimer`: explicitly excludes quantum measurements or process control.

The CPU and CUDA routines compute the same analytic unit-circle series.
Power is 1 by construction. No connection is assumed between this toy IQ series
and the simulated crystallization process. GPU acceleration must be supported
by timing evidence on actual NVIDIA hardware; this repository does not claim it.

## v0.6 QICK readout decision: PROFILE-SPECIFIC FIRST (implemented as intent-only)

QICK readout should initially live in a **separate QICK-specific profile**,
not in the generic QFabric ControlCommand domain API:

1. **Implemented:** Define `QickReadoutIntent` containing target device, ADC/readout channels,
   readout generator binding, frequency, capture length, trigger offset,
   number of repetitions/shots, units, and provenance.
2. **Implemented:** Validate every numeric value and device/channel binding, with bounded
   resource requests. Include compatibility with a pinned upstream source.
3. **Not implemented:** In a separately testable, plan-only profile, map intent to
   `declare_readout`, `trigger`, acquisition intent *only after* their
   source signatures and semantics are verified against pinned QICK.
4. Add synthetic fixture tests, source-shape drift tests and imported-runtime
   signature checks before any executor implementation.
5. Only after an actual hardware-backed integration justifies a
   vendor-neutral observation, design versioned `MeasurementEnvelope`
   with explicit units, time origin, calibration, uncertainty,
   measured/simulated provenance and hardware trace identifiers.

**Current v0.6 still does not compile any QICK readout operation.** It exposes
`qfabric.readoutStatus="intent_only"` to prevent fake acquisitions.

## v0.6 bridge verification

QFabric's CLI supports `--verify` to cross-check a report against the exact
source snapshot bytes. It rejects a different SHA-256, altered input/summary,
unexpected QICK demo calls, non-synthetic analytics, misleading hardware/readout
flags, mismatched shots and incorrect readout proposal fields. The synthetic
snapshot used by CrystalTwinAI's browser example is mirrored at
`tests/fixtures/crystaltwin_snapshot.synthetic.json` to run the offline
generation/verification smoke test on both Python CI versions.

This check is **not a digital signature**, remote attestation, real-measurement
validation or GPU verification. The readout intent remains non-executing.
See [readout intent spec](../adapters/qick-readout-intent.md).

## Safety / reproducibility

- QICK is never instantiated, connected to a board, or invoked. The existing
  planner only emits `declare_gen/add_pulse/pulse` **data**.
- CrystalTwinAI outputs are pedagogical, not validated physical models.
- Samples are mathematically synthetic. There is no measurement fusion,
  feedback loop, control output, sensor calibration or quantum advantage claim.
- Import/export are local files. Neither repository transfers files between
  them automatically or requires tokens.
- Reject non-finite values and unrecognized schemas. Do not load confidential
  research data into public demonstration fixtures.
- Any future remotely hosted service requires auth, rate limits, resource
  quotas, signed hashes, data retention policy and independent science review.

## Submission demo narrative

1. Run existing CrystalTwinAI educational scenario and export a snapshot.
2. Show the SHA-256 / QICK plan preflight in QFabric CLI.
3. Run the **CPU baseline** and, on a verified NVIDIA GPU environment, CUDA
   path with the same shot count; show true backend and measured elapsed time.
4. Import QFabric report into CrystalTwinAI; inspect readout status,
   provenance and computed synthetic IQ summary.
5. Explain that the readout is not physical and the crystallization simulator
   has not been validated against experimental measurements.

## Next engineering milestones

- P0: Cross-repo snapshot/report contract + CPU CI + browser import (v1).
- P1: NVIDIA CUDA run evidence (device ID, elapsed times, environment) and
  repeatable benchmark with warm-up and multiple trials; no speedup claim yet.
- P2: QICK-specific readout API signature audit, fixtures and plan-only compiler (intent-only preflight is implemented in v0.6).
- P3: Optional actual experimental instrumentation interface, separate
  provenance schema and scientific comparability validation.
- P4: Hosted deployment, if contest rules require one, with security review.

## Scope

The private models, training data and scientific accuracy claims of either
project are not expanded by this bridge. Cross-project reuse is by JSON
contract, not copying code between licenses.
