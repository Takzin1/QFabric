# QFabric — source intake and provenance normalization (2026-10-19)

This is a **staging catalog of literature/discovery leads**, **not raw downloaded data**.
It keeps the existing 15 candidates in [the original pinned-file catalog](../../data/quantum_dataset_candidates.json) unchanged, and the separate [QCalEval image-evaluation lane](../../data/quantum_ai_eval_candidates.json) unchanged.

## Files

- [New structured intake](../../data/quantum_source_intake.json) — version `qfabric-quantum-source-intake/1`, seven records: six research-data leads, one simulation/software artifact.
- `src/qfabric/source_intake.py` — Python standard-library-only validation, cross-catalog duplicate source detection, provenance and file-role consistency, immutable unverified status.
- `scripts/quantum_dataset_baseline.py validate-intake` — offline machine-readable status summary; CI on Python 3.11 and 3.12.
- `tests/test_source_intake.py` — negative-path and staging separation regression tests.

## Research source matrix

| Intake ID | Research reference | Track | Suggested filenames (not downloaded) | Meaning and limitations |
| --- | --- | --- | --- | --- |
| QRI-001 | [Cross-platform certification, Zenodo 21775462](https://zenodo.org/records/21775462) / [journal](https://doi.org/10.1038/s41598-025-27248-7) | `cross_vendor_calibration` | Nairobi calibration CSV; IonQ JSON; Brisbane CSV (**actual basenames unknown**) | Hardware/vendor calibration context, not directly commensurable pulse settings. IQM part also described in research; file-by-file source attribution pending. |
| QRI-002 | [Rydberg stabilizer readout, Zenodo 20128631](https://zenodo.org/records/20128631) / [preprint](https://arxiv.org/abs/2605.10924) | `processed_experimental_figures` | `Fig3c.xlsx`, `Fig4.xlsx` | Na/Cs neutral-atom **processed figure** data; **not proven to be original shot records**. |
| QRI-003 | [Superconducting quasiparticle dynamics, Zenodo 11548753](https://zenodo.org/records/11548753) | `noise_time_series` | `Figure3_data.h5` | HDF5 **figure-related** dataset; groups, timestamps, axes and raw-vs-derived classification unknown. |
| QRI-004 | [Color-code MaxSAT, Zenodo 11045522](https://zenodo.org/records/11045522) / [journal](https://doi.org/10.22331/q-2024-10-23-1506) | `decoder_simulation` | `pseudothreshold_plot.csv`, `convergence_rate.txt` | **Simulated decoder results**, not QPU measurements; derive metrics only with documented methods/seeds. |
| QRI-005 | [Parallel Window Decoding, Zenodo 8419215](https://zenodo.org/records/8419215) | `decoder_simulation` | `PW_paper_data.zip` | **Simulated** decoder timing/results; archive contents not inspected; no auto-execution. |
| QRI-006 | [Single-Qubit Quantum Advantage, Zenodo 21896087](https://zenodo.org/records/21896087) | `mixed_research_data` | Experimental code ZIP + simulation code ZIP (**basenames unknown**) | The reported archives contain *code*. They do **not** by themselves prove measured numerical files are downloadable. |
| QRI-007 | [IcePack, Zenodo 19446086](https://zenodo.org/records/19446086) | `software_generator` | `icepack-artifact.zip` | **Software/Stim synthetic generator only**; explicitly excluded from real-data evidence. |

The URLs are version-pinned *record references*, **not verified download links**. Filenames in the catalog are previous literature-discovery leads, not file listings checked afresh at ingestion time. The record's `paperUrl=null` means the associated paper link has **not been independently resolved**, not that the study is invalid.

## Source and artifact modeling

Each **source** is labeled with `track`, `originClaim`, hardware family and source record ID. The **artifacts** then separately carry:

- `role`: `calibration_snapshot`, `processed_figure`, `simulation_output`, `analysis_code` or `software_artifact`.
- `dataOrigin`: `measured_claim`, `mixed_claim`, `simulation_claim`, `tool_only` or `unknown`. These are **upstream characterizations**, not independent QFabric validation.
- `filename`: exact *candidate* basename, or JSON `null` if unknown. **Do not guess the basename** to pass an ingest gate.
- `format`: source-described external format; format-to-filename suffix consistency is validated if basename known.
- `units: null`, `rawSha256: null`, `downloadStatus: not_downloaded` until independently checked.

At the source level `licenseStatus: unverified`, `licenseIdentifier: null`, `reviewStatus: source_lead_only` are **locked**. Adding fake `accepted`, `independently_reproduced`, `rawMeasurement` or `hardwareExecuted` fields fails validation.

**Unit normalization is deferred deliberately.** `T1` in microseconds, `T2` in microseconds, readout assignment error (dimensionless), pulse frequency (Hz), logical error per syndrome round, hardware-specific gate fidelities and simulation pseudo-thresholds are not interchangeable observables. Future normalized columns need:

`{observableName, sourceColumn, numericType, sourceUnit, canonicalUnit, conversionMethod, measurementOrSimulation, device, calibrationTimestamp, shotOrTrialCount, confidenceMethod, sourceFileSha256, sourceRecordVersion, evidenceLevel}`

This is a **proposed field mapping contract**, **not a schema or numerical measurement already supported by executable code**. Time bases, uncertainty model and physical hardware configuration must be resolved per experiment.

## Local verification (no network)

```bash
python -m pip install -e ".[dev]"
python scripts/quantum_dataset_baseline.py validate-catalog data/quantum_dataset_candidates.json
python scripts/quantum_dataset_baseline.py validate-ai-catalog data/quantum_ai_eval_candidates.json
python scripts/quantum_dataset_baseline.py validate-intake data/quantum_source_intake.json --catalog data/quantum_dataset_candidates.json
pytest tests/test_source_intake.py -q
ruff check .
```

The summary counts research leads and file *leads*, not acquired experiment files. A passing validator is **metadata consistency only**, and never a quality score.

## Next gates for measured/numerical baselines

1. Resolve publication DOI/Zenodo version and inspect the source's *actual* filenames, byte sizes, documentation, restrictions and per-file license.
2. Download to a non-repository working area with explicit resource limits and compute the **actual** SHA-256; compare published checksums independently. Preserve original bytes.
3. Parse only vetted CSV/XLSX/HDF5 fields with safe parsers. Never execute a downloaded Jupyter notebook, Python package or ZIP scripts as part of discovery.
4. Extract figure-level plotted values separately from raw shot events; do not train on mixed simulations while claiming hardware measurements.
5. Determine device-specific field mappings, missing values, units, time and calibration configuration **from source evidence**.
6. Only then promote to a separately versioned validated-evidence contract, with paper-specific reproducibility comparisons, numerical deltas, tolerances and software versions. Do not silently merge external QPU calibrations into QICK hardware commands.

**Current counts:** 7 source leads, 12 artifact leads, 0 downloaded, 0 scientifically reproduced, 0 hardware dispatches. The initial 15 pinned-file candidates stay separate; therefore this work is not claiming 22 validated scientific datasets.
