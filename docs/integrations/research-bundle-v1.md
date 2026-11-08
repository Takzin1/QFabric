# QFabric × CrystalTwinAI — reproducible offline research bundle v1

**Scope (2026-11-08):** inspectable **synthetic** interoperability experiment.
No quantum hardware, crystallization equipment, physical measurement, or
scientific replication is exercised. The bundle is a local run card, **not**
independent authentication of research provenance.

## Reproduce the complete CPU-only experiment

Run at the root of QFabric on Python 3.11 or 3.12:

```bash
python -m pip install -e ".[dev]"
pytest
python scripts/crystaltwin_bridge.py tests/fixtures/crystaltwin_snapshot.synthetic.json /tmp/ctqf-report.json --backend cpu --shots 256
python scripts/crystaltwin_bridge.py tests/fixtures/crystaltwin_snapshot.synthetic.json /tmp/ctqf-report.json --verify
python -m scripts.research_bundle tests/fixtures/crystaltwin_snapshot.synthetic.json /tmp/ctqf-report.json /tmp/ctqf-bundle.json
python -m scripts.research_bundle tests/fixtures/crystaltwin_snapshot.synthetic.json /tmp/ctqf-report.json /tmp/ctqf-bundle.json --verify
```

The manifest records exact SHA-256 of the snapshot **and** report, a
pair-derived run ID, explicit endpoint, declared CPU/CUDA backend and shots.
It is deterministic **for those exact two byte sequences**. The upstream bridge
report has a generation timestamp, so a second run normally has a different
report hash and run ID. Do not assert bit-for-bit repeatability of the entire
time-stamped report without controlling that field.

QFabric validates the report's exact input hash, synthetic IQ invariants,
intent-only readout and pinned plan shape **before** writing the manifest.
Manifest verification regenerates expected fields from the raw files. A
modified report, swapped snapshot, fake measured status or falsified result
fails closed. Manifest creation refuses to overwrite an existing path.

The manifest schema `ctqf-research-bundle/1` is also checked in CrystalTwinAI
by `src/lib/research-run-bundle.ts`, against the same exact UTF-8 source and
report texts. The browser-side checker performs local SHA, reported
input/summary consistency, bounded parsing and non-execution assertions.
**The Python CLI remains the fuller QICK plan semantic verifier**.

## Literature → testable research stages

| Track | Pinned primary lead in existing repositories | Required independent validation |
| --- | --- | --- |
| CrystalTwinAI numerical solver | Zhang et al. (2024), DOI [10.1016/j.compchemeng.2024.108612](https://doi.org/10.1016/j.compchemeng.2024.108612) | Constant-growth PBE exact-solution L1, particle conservation and grid convergence; never call this experimental calibration |
| CrystalTwinAI empirical source | BigSolDB v2.2 dataset record [10.5281/zenodo.22648301](https://doi.org/10.5281/zenodo.22648301) | Original bytes, concentration basis, polymorph/method, DOI and held-out measurements |
| QFabric control/compatibility | [QICK upstream reference](https://github.com/openquantumhardware/qick) pinned by the plan profile | Pinned runtime signature, upstream API drift, device-specific execution gates (hardware currently out of scope) |
| QFabric alternative performance baseline | Proctor et al., PRL (2022), DOI [10.1103/PhysRevLett.129.150502](https://doi.org/10.1103/PhysRevLett.129.150502) | Obtain original archive, checksum, circuit families and controls; mirror RB is **not** equal to QEC logical error |
| QFabric spectator errors | Govia et al., NJP (2023), DOI [10.1088/1367-2630/ad0e19](https://doi.org/10.1088/1367-2630/ad0e19) | Matched intermediate-measurement/no-measurement comparison with spectator errors |
| QFabric correlated-error caveat | Google Quantum AI, Nature (2025), DOI [10.1038/s41586-024-08449-y](https://doi.org/10.1038/s41586-024-08449-y) | Check source corrections, correlated trials and bootstrap design; never apply simple independent Bernoulli rates without audit |

These are **methodological/source leads**, not datasets ingested or results
replicated by this manifest feature. Verify publication metadata and full
texts at the original publishers before scholarly submission.

## Proposed scientific experiment (not yet run)

**RQ:** Can provenance-bound agent proposals remain interoperable across a
classical crystal-process simulator and a quantum-control planning layer
while rejecting contradictory or misleading evidence?

Predeclare three cases: (1) valid synthetic bridge passes; (2) one source
byte changes and fails; (3) one physical-execution or readout claim changes
and fails. Report pass/fail **per case**, not as evidence of a physical
accuracy, quantum speedup or trustworthy AI author.

For real papers, separate two domain-specific evaluations rather than
mixing metrics: CrystalTwinAI uses temperature/PSD/induction-time error
under comparable conditions, QFabric uses predeclared hardware-family
and circuit-appropriate observables. Quantify uncertainty, independent
holdout and failure domains before any real-world performance claim.

## Required next gate

Original raw experimental files with legal reuse rights and verifiable
SHA-256, provenance and units. They are **not included** in this update.
Do not promote bibliography entries or synthetic fixtures into measured
evidence. The QICK backend remains **plan-only**.
