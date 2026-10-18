# QICK readout intent v0.6 — bounded, profile-specific and non-executing

## Decision

QFabric does **not** introduce a generic quantum measurement API at v0.6.
Different QPU types have different readout physics, clocks and digitizer
semantics. The first boundary is **QICK-specific**, descriptive and strictly
separate from `QickPlanAdapter.compile`.

`QickReadoutIntent` lives in `src/qfabric/profiles/qick_readout.py`.
`QickReadoutPlanner` checks explicit logical device and channel allowlists,
and returns `QickReadoutPlan`, whose `to_dict()` produces JSON-friendly data.

No QICK package is imported. The returned object contains **no callable
control operations** and can never be passed to an executor by this package.

## Inputs and units

| Field | Meaning | Software bounds |
| --- | --- | --- |
| `device_id` | Logical experiment target | Non-empty string |
| `readout_gen_ch` | Explicitly bound hypothetical generator | Integer 0–65535 |
| `adc_channels` | Explicitly bound ADC channels | Non-empty tuple of 1–16 unique integers 0–65535 |
| `frequency_mhz` | Proposed readout frequency (MHz) | Finite 0–1,000,000 |
| `capture_length_us` | Proposed acquisition window (µs) | Finite >0 and <=1,000,000 |
| `trigger_offset_us` | Proposed trigger offset (µs) | Finite 0–1,000,000 |
| `shots` | Proposed repetitions | Integer 1–2,000,000 |
| `calibration_ref` | Declared calibration label | Non-empty, <=128 chars; defaults to `unverified` |

**Bounds are resource guards, not guaranteed safe hardware limits.** In
particular, an accepted frequency does not establish that a board supports it;
trigger offsets are neither cycle-aligned nor compared to a real RFSoC clock.
There is no digitizer data, IQ demodulation model, quantum state estimate,
hardware timing guarantee, or calibrated measurement uncertainty.

## Example

```python
from qfabric.profiles import QickReadoutIntent, QickReadoutPlanner

planner = QickReadoutPlanner(
    device_id="qick-demo-no-hardware",
    generator_channels=(0,),
    adc_channels=(0,),
)
proposal = planner.plan(QickReadoutIntent(
    device_id="qick-demo-no-hardware",
    readout_gen_ch=0,
    adc_channels=(0,),
    frequency_mhz=100.0,
    capture_length_us=1.0,
    trigger_offset_us=0.0,
    shots=256,
))
assert proposal.to_dict()["status"] == "intent_only"
assert proposal.to_dict()["hardwareExecuted"] is False
```

## Integration and integrity

The CrystalTwinAI bridge generates this v0.6 proposal while retaining the
existing `qfabric-crystaltwin-report/1` report envelope for compatibility
with the browser importer. `readoutIntent` preserves `kind`, `shots` and
`note`, adding bounded parameters and `status: intent_only`.

For an independent snapshot **byte-for-byte** cross-check:

```bash
python scripts/crystaltwin_bridge.py snapshot.json report.json --backend cpu --shots 256
python scripts/crystaltwin_bridge.py snapshot.json report.json --verify
```

`--verify` checks the original input SHA-256, source labels, payload summary,
the exact expected QICK **demo-only** pulse plan, the readout proposal,
synthetic analytics and non-execution declarations. This is a reproducible
consistency check, **not** an electronic signature or authenticity proof.
It does not prove CUDA utilization or benchmark throughput.

## Deliberately excluded until hardware audit

- Mapping to upstream `declare_readout`, `trigger`, `acquire` methods.
- Program object instantiation, memory allocation, acquisition or RFSoC I/O.
- Generic measurement envelopes, real telemetry or quantum state inference.
- Mixing synthetic IQ waveforms with crystallization process measurements.
- Autonomous experiment control or model-driven equipment commands.

Before extending the plan compiler, pin actual upstream QICK readout method
signatures and semantic documentation, add source-drift fixtures and runtime
signature-binding tests, and require explicit operator review before any
physical execution. Consider a versioned vendor-neutral result envelope only
after independent evidence supports shared semantics across at least two
hardware families.
