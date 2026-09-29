# QICK plan profile

QFabric v0.3 includes a **plan-only** backend profile for the open-source
[QICK: Quantum Instrumentation Control Kit](https://github.com/openquantumhardware/qick).

This profile does not import QICK, instantiate a QICK program, connect to an RFSoC,
or execute a pulse. It translates a narrow QFabric command subset into a declarative
sequence of QICK API-shaped calls that can be inspected and tested without hardware.

## Upstream reference

The profile was reviewed against:

- repository: `openquantumhardware/qick`
- commit: `4da51a5154e448fa3613257a967bfa6a58959a8b`
- upstream commit date: 2026-09-16
- public documentation path:
  `docs/source/topics/playing_pulses.rst`

At that reference point, the QICK documentation describes the tProc v2 pulse flow as:

1. `declare_gen(...)`
2. `add_pulse(...)`
3. `pulse(...)`

The upstream README also states that QICK is actively developed and does not guarantee
backward compatibility for all updates. QFabric therefore pins the upstream reference
commit in every generated plan rather than claiming compatibility with arbitrary QICK
versions.

## Supported mapping

Profile version: `0.1.0`.

Only QICK `const` pulses are supported.

| QFabric field | QICK plan field | Rule |
| --- | --- | --- |
| logical `channel` | generator `ch` | explicit `QickGeneratorBinding` required |
| `value` | `gain` | unit MUST be `normalized_gain`; range [-1, 1] |
| `duration_s` | `length` | converted from seconds to microseconds |
| `qick.frequency_mhz` | `freq` | required numeric metadata |
| `qick.phase_deg` | `phase` | optional; defaults to 0 degrees |
| `qick.time_us` | `t` | required non-negative numeric metadata |
| `qick.style` | `style` | optional; only `const` accepted |

Pulse names are generated deterministically as `qf_0000`, `qf_0001`, and so on.

Generator declarations are emitted once per bound QICK generator channel.

## Example

~~~python
from datetime import UTC, datetime

from qfabric.models import ControlCommand, ExperimentRequest
from qfabric.profiles.qick import QickGeneratorBinding, QickPlanAdapter
from qfabric.protocol import CommandEnvelope

adapter = QickPlanAdapter(
    device_id="qick-lab-01",
    bindings=(
        QickGeneratorBinding(
            logical_channel="drive",
            gen_ch=0,
            nqz=1,
        ),
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
        ),
    ),
)

plan = adapter.compile(envelope)

for call in plan.calls:
    print(call.method, dict(call.kwargs))
~~~

The resulting plan contains:

~~~text
declare_gen(ch=0, nqz=1)
add_pulse(ch=0, name="qf_0000", style="const",
          freq=100.0, phase=0.0, gain=0.5, length=1.0)
pulse(ch=0, name="qf_0000", t=0.0)
~~~

This is descriptive plan output only. QFabric does not dispatch these calls to QICK.

## Explicit limitations

The v0.1 QICK profile does **not** currently support:

- `arb` or `flat_top` pulses
- Gaussian, triangle, cosine, or DRAG envelope helpers
- `declare_readout`, `trigger`, or acquisition
- QICK sweeps or loops
- generator capability discovery from a live `soccfg`
- validation against a physical board's firmware configuration
- pulse-overlap or timing-resource analysis
- waveform-memory limits
- transport, board connection, or RFSoC execution
- claims of compatibility with any specific QICK hardware deployment

Those features should be added only when their semantics can be tested against a pinned
QICK release or controlled hardware fixture.

## Compatibility claim

The precise v0.3 claim is:

> QFabric can deterministically translate a constrained QFabric command envelope into
> a call plan shaped like the documented QICK tProc v2 `declare_gen` /
> `add_pulse` / `pulse` API at upstream commit
> `4da51a5154e448fa3613257a967bfa6a58959a8b`.

It is **not** a claim that QFabric has driven QICK hardware.

## Why plan-only first?

Keeping compilation separate from execution provides three useful boundaries:

1. plans can be reviewed before they reach hardware;
2. CI can test mapping logic without an RFSoC or vendor runtime; and
3. upstream API drift can be detected as a compatibility problem rather than silently
   reaching a physical device.

A future executor may consume these plans, but execution must remain an explicit,
separately tested boundary.
