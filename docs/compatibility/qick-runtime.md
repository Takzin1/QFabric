# Controlled QICK runtime compatibility

QFabric v0.5 adds a runtime-level compatibility check for the pinned QICK planning
profile.

This layer is intentionally stronger than source-only drift inspection and
intentionally weaker than hardware execution.

## Three compatibility levels

QFabric keeps three claims separate:

1. **Source-shape compatibility**
   - AST inspection of upstream source
   - no QICK import
   - detects class/method/signature drift

2. **Imported-runtime compatibility**
   - installs the pinned QICK package
   - imports the real Python classes
   - verifies that QFabric-generated keyword calls bind to real method signatures
   - no object construction or hardware I/O

3. **Hardware compatibility**
   - not claimed by v0.5
   - requires a separately designed executor, controlled hardware fixture, and
     explicit hardware-specific validation

Passing level 2 does not imply level 3.

## Pinned runtime

The controlled fixture uses:

- repository: `openquantumhardware/qick`
- commit: `4da51a5154e448fa3613257a967bfa6a58959a8b`
- expected package version: `0.2.432`

The fixture runs on CPU-only GitHub Actions.

QICK's packaging only installs PYNQ on supported ARM architectures, so the CPU CI job
can import the non-hardware control modules without loading RFSoC drivers.

## What is imported

The fixture imports:

- `qick`
- `qick.qick_asm`
- `qick.asm_v2`

It reads these runtime methods:

- `AbsQickProgram.declare_gen`
- `QickProgramV2.add_pulse`
- `AsmV2.pulse`

No QICK program object is instantiated.

## What is validated

QFabric first generates a normal `QickExecutionPlan`.

For each plan call, v0.5 obtains the real runtime method signature with
`inspect.signature()` and attempts:

~~~python
signature.bind(None, **call.kwargs)
~~~

The leading `None` occupies the unbound `self` parameter. The method itself is never
called.

This verifies that the installed runtime accepts the exact keyword-call shape QFabric
would use.

For the current profile:

- `declare_gen(ch=..., nqz=...)`
- `add_pulse(ch=..., name=..., style=..., freq=..., phase=..., gain=..., length=...)`
- `pulse(ch=..., name=..., t=...)`

## Version check

The runtime report also checks that `qick.__version__` equals `0.2.432`.

A different installed version is reported as incompatible for the pinned fixture even
if the signatures still bind. Latest-upstream compatibility belongs to the separate
drift-watch layer.

## CI

`.github/workflows/qick-runtime.yml` runs:

- on relevant pull requests
- on relevant pushes to `main`
- manually through `workflow_dispatch`

The job:

1. installs QFabric;
2. installs QICK from the pinned commit;
3. prints the imported QICK package version;
4. builds a deterministic QFabric const-pulse plan;
5. binds every generated call to the real QICK runtime signatures;
6. fails if import, version, or call binding is incompatible.

## Non-goals

The v0.5 runtime fixture does not:

- instantiate `QickProgramV2`
- construct a board configuration
- connect to a QICK server
- connect to an RFSoC
- allocate hardware resources
- dispatch `declare_gen`, `add_pulse`, or `pulse`
- compile a complete hardware program
- acquire data
- validate firmware
- prove pulse timing or physical correctness

Those are future validation layers and require a separate safety and reproducibility
design.

## Why this layer matters

Source inspection can miss runtime import problems or packaging differences. Hardware
testing is too strong a first response to every software change.

The runtime-binding fixture fills the middle:

~~~text
Source contract
      |
      v
Imported runtime
      |
      v
Call binding
      |
      v
Future controlled executor
      |
      v
Future hardware validation
~~~

This keeps compatibility claims narrow, reproducible, and testable at each layer.
