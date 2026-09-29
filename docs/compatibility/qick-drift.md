# QICK upstream drift semantics

QFabric's QICK profile is pinned to a known upstream reference for traceability, but
compatibility is not defined as "the upstream commit SHA must never change."

That would be too strict for an actively maintained dependency.

## Reference point

The v0.4 compatibility contract records:

- repository: `openquantumhardware/qick`
- reference commit: `4da51a5154e448fa3613257a967bfa6a58959a8b`
- inspected methods:
  - `AbsQickProgram.declare_gen`
  - `QickProgramV2.add_pulse`
  - `AsmV2.pulse`

The baseline signature is stored in
`compat/qick/api_contract.json`.

## What QFabric actually requires

The plan profile emits only these QICK call keywords:

- `declare_gen`: `ch`, `nqz`
- `add_pulse`: `ch`, `name`, `style`, `freq`, `phase`, `gain`, `length`
- `pulse`: `ch`, `name`, `t`

The drift harness therefore checks whether the observed upstream methods can still
accept those keywords.

A method may accept a keyword explicitly or through `**kwargs`.

## Stable, compatible drift, and breaking drift

The report has two independent signals:

- `drifted`: the observed signature differs from the pinned baseline
- `compatible`: QFabric's required call shape is still accepted

This creates three meaningful states:

| State | Meaning | CI result |
| --- | --- | --- |
| PASS / STABLE | upstream shape matches the pinned baseline | success |
| PASS / DRIFT | upstream changed, but QFabric's generated calls remain acceptable | success |
| FAIL / DRIFT | upstream no longer accepts a required QFabric call shape | failure |

For example, adding a new optional parameter to `declare_gen` is drift but does not
necessarily break QFabric. Renaming `ch` to `channel` without accepting `ch`
would be breaking for the current profile.

## Why AST instead of text matching?

The checker parses Python source with the standard-library `ast` module. This avoids
false failures caused by formatting, line wrapping, or whitespace changes.

The contract compares:

- class name
- method name
- accepted parameter names and kinds
- baseline defaults for drift reporting
- presence of `**kwargs` when it provides keyword compatibility

No QICK module is imported.

## Weekly watch

`.github/workflows/qick-drift.yml` runs weekly and can also be started manually.

The workflow:

1. checks out QFabric;
2. installs the local QFabric package;
3. shallow-clones the latest `openquantumhardware/qick` main branch;
4. records the observed upstream commit;
5. runs `scripts/check_qick_drift.py` against that source tree.

The watch never connects to an RFSoC and never executes a QICK program.

## Local usage

~~~bash
git clone https://github.com/openquantumhardware/qick.git /tmp/qick
python scripts/check_qick_drift.py --root /tmp/qick
~~~

Exit code is zero while the required QFabric call shape remains compatible. Breaking
drift returns a non-zero exit code so CI can stop the pipeline visibly.

## Limits

This harness does not prove behavioral or hardware compatibility. A method may retain
the same Python call signature while changing semantics internally.

The drift watch therefore protects the **source-level integration contract** only.
A controlled QICK runtime fixture is the next validation layer before any physical
execution claim.
