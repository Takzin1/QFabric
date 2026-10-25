# QFabric contributor and coding-agent instructions

## Scope
QFabric is an experimental, vendor-neutral quantum-control **planning**
project. Read `CONTRIBUTING.md` and the files/callers affected by a change
before editing. Check existing helpers, tests, fixtures, protocol schemas and
documentation before introducing a new layer.

## Smallest complete change (Ponytail-inspired)
1. If a feature is not required for the task, do not implement it.
2. Reuse existing code and project conventions before creating abstractions.
3. Prefer the Python standard library over new dependencies.
4. Keep a change localized; fix the cause rather than adding an adapter to hide it.
5. Change callers, tests, fixtures and docs together if their contracts change.
6. Delete unnecessary code where doing so is demonstrably safe.
7. Run `ruff check .` and `pytest` for behavioral edits; preserve CI smoke tests.

Minimize **complexity**, not required validation. Do not remove guards or
make obscure one-liners just to reduce line count.

## Non-negotiable scientific and safety boundaries
- The core must stay free of QICK, NVIDIA and other vendor SDK imports.
- QICK call compilation is **plan-only**. Never add `acquire`, `trigger`,
  RFSoC I/O or physical execution without an explicit independent task,
  hardware-specific verification and operator-controlled design.
- Model-generated text/JSON and public research files are untrusted inputs.
  Preserve size limits, strict parsing, finite-number checks, device/channel
  allowlists, evidence hashes and refusal paths. Never run fetched code.
- Keep `measured`, `simulated`, `synthetic` and `inferred` provenance distinct.
  A hash proves byte consistency, not authenticity; a self-attested review is
  not authenticated approval.
- Do not assert real NVIDIA GPU speedup, actual quantum measurements, hardware
  compatibility, scientific validation or Nebius/Nemotron inference without
  independent executed evidence.
- Preserve `qfabric-crystaltwin-report/1`,
  `crystaltwin-qfabric-snapshot/1` and `qfabric-research-proposal/1`
  contracts unless a versioned migration and tests are part of the task.
  After changing `qfabric.orchestration`, regenerate
  `tests/fixtures/research_gate_golden.json` (scripts/export_gate_golden.py)
  and copy it to CrystalTwinAI's TypeScript port tests.
- Do not download, commit or redistribute third-party datasets without
  verifying license, provenance, file integrity and appropriate retention.

## Review checklist
Before opening a PR, answer briefly:
- What existing helper or standard-library path did you reuse?
- Is each new dependency/file/configuration actually necessary?
- Which trust boundaries, compatibility guarantees and downstream callers
  could break?
- Which tests or CI jobs establish what **really** works? What was not tested?

For documentation-only changes, avoid creating arbitrary runtime code or
installing lifecycle hooks.

## Upstream inspiration and limits
Development principles adapted for this repository from
[DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail)
(MIT-licensed, copyright 2026 Dietrich Gebert). This file is a
QFabric-specific *instruction-only* adaptation, not an upstream plugin
installation or executable dependency. No third-party hooks are installed.
