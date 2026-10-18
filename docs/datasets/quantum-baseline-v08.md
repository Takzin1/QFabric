# QFabric v0.8 — Quantum Dataset Candidate Registry and Statistical Baseline

**Checked:** 2026-10-19 (JST). **Baseline maturity:** metadata-only candidate catalog + entirely **synthetic** binomial reference. No quantum dataset file was successfully downloaded or analyzed in this development step. Claims in a published record have not been verified against raw data.

## 1. Main outputs

- [Machine-readable dataset candidate catalog](../../data/quantum_dataset_candidates.json): 15 pinned Zenodo record versions/file names with source paper URL, DOI, published MD5 strings (where visible), measurement-vs-simulation **record-supplied claim**, and explicit unknown status for license, units, raw SHA-256 and ingestion.
- [Small, synthetic count fixture](../../tests/fixtures/quantum_counts.synthetic.json): intentionally artificial `shots/errors` counts; **not** any laboratory results.
- `src/qfabric/dataset_baseline.py`: zero new dependencies, strict JSON/catalog validation plus Wilson 95% binomial calculation.
- `scripts/quantum_dataset_baseline.py`: human-readable standalone CLI.

## 2. Source exploration and priority

| ID | Priority | Main source link | Suggested first file | Record classification | Verification needed |
| --- | --- | --- | --- | --- | --- |
| QRD-001 | P0 | [Caune et al. QEC, Zenodo v2](https://zenodo.org/records/15364358) / [arXiv](https://arxiv.org/abs/2410.05202) | `fig4b_decoding_response_time.csv` 917 B | measured claim | Confirm timing column units and figure correspondence |
| QRD-005 | P0 | [Marciniec et al. quantum-dot reset](https://zenodo.org/records/16616153) / [arXiv](https://arxiv.org/abs/2510.25703) | `fig2b_active_reset.xlsx` 24.2 kB | measured claim | Inspect workbook cells; avoid assigning units by inference |
| QRD-006 | P0 | [Agarwal et al. non-Markovian noise](https://zenodo.org/records/8363718) / [peer-reviewed DOI](https://doi.org/10.1088/2058-9565/ad3d7e) | `modelling_non_markovian_noise_in_driven_superconducting_qubits_experiment_results.csv` 832.5 kB | measured claim | Use README to interpret columns, run original paper-specific comparison |
| QRD-007 | P0 | [Drotos et al. raw count experiments](https://zenodo.org/records/10723401) | `pm_umbrella_prepcert_counts_all.zip` 17.2 kB | measured claim | Safely extract count CSV and accompanying metadata PDF |
| QRD-008 | P0 | [Li et al. autonomous QEC](https://zenodo.org/records/20768851) / [arXiv](https://arxiv.org/abs/2504.16746) | `QEC data.zip` 26.3 kB | mixed claim | Differentiate plotted experimental data and theoretical simulation |
| QRD-009 | P1 | [Zhang et al. tunable couplers](https://zenodo.org/records/16791932) | `Dataset_TuanbleCoupler_aSWAP.zip` 17.8 MB | mixed claim | Keep raw, processed and Python code separate; never execute imported code |
| QRD-010 | P1 | [Scriva et al. measurement shot noise](https://zenodo.org/records/8223528) / [journal DOI](https://doi.org/10.1103/PhysRevA.109.032408) | `data.tar.gz` 870 kB | mixed claim | Interpret VQE/QAOA modeling assumptions; not asserted hardware measurements |
| QRD-011 | P1 | [Guo et al. variational readout](https://zenodo.org/records/20267133) | `data.zip` 25.4 MB | mixed claim | Identify experimental vs post-processed vs theoretical files |
| QRD-012 | P2 | [Google Quantum AI surface-code scaling](https://zenodo.org/records/6804040) | `google_qec3v5_experiment_data.zip` 315.5 MB | measured claim | Study READMEs and decoding protocol before heavy download |
| QRD-013 | P1 | [Miao et al. leakage QEC](https://zenodo.org/records/7302032) / [journal DOI](https://doi.org/10.1038/s41567-023-02226-w) | `readout_clouds.zip` 86 kB | measured claim | Inspect figure source / IQ data correspondence, distinct from simulation archives |
| QRD-014 | P1 | [Stein IBM calibration/QEC](https://zenodo.org/records/20768087) | `ibm_fez.tar.gz` ~9 MB | measured claim | Never treat IBM calibration as QICK hardware calibration |
| QRD-015 | P1 | [Zhang and Xie logical QEC mitigation](https://zenodo.org/records/17744500) | `data_for_demonstrating_quantum_error_mitigation_on_logical_qubits.zip` 113 kB | mixed claim | Separate experimental vs numerical plotted data |
| QRD-016 | P1 | [Beaulieu et al. transmon readout](https://zenodo.org/records/20825189) | `Zenodo.zip` 31.3 MB | measured claim | Confirm paper publication, units and raw/processed distinctions |

*All rows: license unverified; exact raw-file SHA-256 unverified; original numeric contents not downloaded.* `publishedMd5` is a hash **claimed by Zenodo's file listing**, not a local independent match, and does not replace SHA-256 of retrieved bytes.

**Additional watchlist (not yet in machine-readable manifest):**
- [Google surface code leakage, simulation/experiment ZIPs](https://zenodo.org/records/7302032) — separate physical vs simulated subsets; large archives are inappropriate for a first ingestion milestone.
- [QDataSet — simulated quantum control/noise, Scientific Data](https://doi.org/10.1038/s41597-022-01639-1) / [GitHub](https://github.com/eperrier/QDataSet) — simulation, not a lab observation. Select tiny reproducible sample, not full dataset.
- [Quantum-dotted nanosecond pulse distortion figure code](https://zenodo.org/records/18511000) — record says *raw measurements available upon reasonable request*. **Not directly obtainable** through listed code archive; do not call this a raw dataset.
- [Autonomous QEC 2026](https://zenodo.org/records/20768851) — tiny archive, but plotted values versus raw measurements must be classified separately.

## 3. Baseline definition: what is and is NOT being tested

A local fixture contains two synthetic groups: `(100 shots, 5 errors)` and `(200 shots, 30 errors)`. The reference statistic is `errorRate = errors / shots`, with a *nominal* 95% Wilson score interval using `z = 1.959963984540054`:

\[
\hat{p}=k/n,\quad
\text{CI}_{Wilson}=
\frac{\hat{p}+z^2/(2n)}{1+z^2/n}
\pm\frac{z\sqrt{\hat{p}(1-\hat{p})/n+z^2/(4n^2)}}{1+z^2/n}.
\]

| Synthetic group | Shots | Errors | Error rate | Wilson 95% interval |
| --- | ---: | ---: | ---: | --- |
| low-error | 100 | 5 | 0.05 | [0.0215436792, 0.1117504692] |
| high-error | 200 | 30 | 0.15 | [0.1071359356, 0.2060557928] |

**Critical caveats:** Wilson coverage presumes independent binomial/Bernoulli samples, which may not hold for correlated syndrome measurements, time-varying drift, repeated decoder rounds or class-imbalanced readout. The synthetic result is a **software arithmetic/validation baseline**, **not** an empirical QEC fidelity, logical error per round, validated readout result, or a reproduction of any paper. Never compare this toy rate directly against those papers' published numbers. Define the proper observable and statistical unit from each experiment before using raw data.

## 4. Reproduce offline

```bash
python -m pip install -e ".[dev]"
python scripts/quantum_dataset_baseline.py validate-catalog data/quantum_dataset_candidates.json
python scripts/quantum_dataset_baseline.py synthetic-baseline \
  tests/fixtures/quantum_counts.synthetic.json --output synthetic-baseline.json
python -m pytest tests/test_dataset_baseline.py -q
ruff check .
```

The output records the **exact fixture input SHA-256** and includes `measurementVerified=false`, `hardwareExecuted=false`. Catalog validation reports `downloadedDatasets=0` and `validatedMeasurements=0`. No external network access is required.

## 5. Acceptance criteria for a *future* measured baseline

The v0.8 catalog is intentionally **candidate-only** and refuses any entry pretending to have a verified license, checked units, downloaded data or raw SHA-256. The *next* implementation should use a separate versioned evidence schema, not silently promote metadata:

1. Obtain source files from the pinned data record; keep original bytes immutable and record a new locally **computed** SHA-256 and acquisition time. Compare Zenodo-listed MD5 where available.
2. Inspect actual paper's experimental setup, measurement unit, axes, calibration state, sample independence, data dictionary and README. Mark gaps `unknown`.
3. Audit each dataset/file license and any commercial redistribution restrictions. Until then, **do not commit third-party raw files** to this repository.
4. Parse untrusted files using size/time bounds, safe archive traversal, decompression limits, no shell execution or Python pickle. Optional HDF5/XLSX dependencies only when concrete source formats require them.
5. Distinguish raw measured events, post-processed metrics, simulated values, extracted-from-figure data and NotebookLM's inferred summary; attach per-column provenance.
6. Build a dataset-specific, preregistered method: exact filtering, observable, uncertainties, rounding, and measurement time basis. Compare recomputed output to the **same** original paper figure/table with explicit deltas and tolerance justified scientifically.
7. Only then permit status `independently_reproduced`, storing version/commit/runtime and all intermediate hashes. Do **not** translate external IBM, Google, trapped-ion or quantum-dot data into QICK calls automatically.

## 6. NotebookLM / Nemotron boundaries

NotebookLM can help extract *citations, labels and conditions* from paper PDFs and metadata; imported summaries are `unverified_extraction` until the original document is checked. Nemotron may propose a hypothesis citing **verified** evidence, but QFabric's v0.7 human review remains required; neither can create measured data or hardware capabilities.

**Unimplemented:** internet download, paper PDF ingestion, NotebookLM connection, model inference, physical QPU coupling, experimental reproduction. Any reported numeric reference in this document comes from the **synthetic** counts fixture.


## 7. 2026-10-19 dataset expansion and local integrity

This updates the Zenodo **candidate-only** catalog to 15 records; not 15 ingested or reproduced experiments.

| ID | Track | Source | Suggested file | Outstanding gates |
| --- | --- | --- | --- | --- |
| QRD-017 | FPGA quantum decoder benchmarks | [Riverlane Zenodo 11621878](https://zenodo.org/records/11621878) | fpga_memory_data.csv (~205 B, source listing claim) | Real FPGA vs simulation subsets, unit definitions, DOI, checksum, rights |
| QRD-018 | Silicon-spin-qubit experiment | [Diraq public v2 Zenodo 17518472](https://zenodo.org/records/17518472) | ExtData_Fig4.csv (~772 B, source listing claim) | Prior v1 is restricted; never silently merge versions; original columns/units, checksum, rights |
| QAE-001 | **AI image evaluation; not quantum numerical measurements** | [NVIDIA QCalEval data](https://huggingface.co/datasets/nvidia/QCalEval) / [scripts](https://github.com/NVIDIA/QCalEval) | No downloaded file yet | Dataset revision, per-item provenance, image rights, scores, SHA-256 |

**Deferred / watchlist:** [Zhang superconducting gate data, Zenodo 17541057](https://zenodo.org/records/17541057) (~40.4 MB archive reported; exact filename and archive rights not checked), [Shi quantum-simulator figures, Figshare 22802981](https://figshare.com/articles/dataset/_/22802981) (non-Zenodo repository), [Stanford quantum-router data, Zenodo 16954111](https://zenodo.org/records/16954111) (large archive). None is represented as a downloaded or verified manifest entry.

### Why QCalEval is a separate evaluation track

The [official NVIDIA QCalEval README](https://github.com/NVIDIA/QCalEval/blob/main/README.md) describes Q1–Q6: plot description, experiment outcome, scientific reasoning, fit reliability, parameter extraction, calibration diagnosis. It explicitly states **Apache-2.0 for evaluation scripts** and **CC-BY-4.0 for the dataset**. These are upstream license *claims* confirmed in the README, not a file-by-file audit. A code license is not the data license. QCalEval includes mixed-origin calibration plots; its benchmark scores (none executed here) are **not actual quantum measurement error rates**.

The [dedicated AI evaluation candidate catalog](../../data/quantum_ai_eval_candidates.json) has schema qfabric-quantum-ai-evaluation-candidates/1. The Zenodo physical data catalog retains qfabric-quantum-dataset-candidates/1. The two parsers deliberately reject each other's schema.

### Local byte audit — new offline implementation

After independently obtaining and legally using an original source file, audit its bytes without parsing CSV, images or archives:

~~~bash
python scripts/quantum_dataset_baseline.py validate-catalog data/quantum_dataset_candidates.json
python scripts/quantum_dataset_baseline.py validate-ai-catalog data/quantum_ai_eval_candidates.json
python scripts/quantum_dataset_baseline.py audit-local-file data/quantum_dataset_candidates.json QRD-017 /path/to/fpga_memory_data.csv --output local-audit.json
~~~

The local-file audit:
- requires exact dataset ID and filename, rejects symlinks/non-regular files, caps input at 32 MiB and detects many concurrent changes;
- computes SHA-256 and MD5 on the same **locally supplied** bytes; compares against provider-published MD5 if available; fails closed on mismatch;
- explicitly reports provider-checksum-absent cases as such;
- does **not** download, parse, extract, execute, rehost or publish source data;
- always reports dataParsed=false, datasetAccepted=false, measurementVerified=false, scientificallyReproduced=false, unitsVerified=false, licenseVerified=false and hardwareExecuted=false.

**MD5 matching is not authenticated provenance.** SHA-256 establishes locally observed byte identity, not scientific reproducibility, file rights or dataset validity. The default audit size limit excludes the larger Zhang ZIP pending a separate scoped and safely bounded parser.

### Gate for a future real-data baseline

An experimental result must first have a pinned paper and record version, documented file license, independently checked raw-file bytes and hash, actual field names/units, measurement-vs-simulation categorization, original publication method, and a justified numerical comparison/tolerance. A separately versioned verified-evidence contract is required before advancing beyond candidate status. QCalEval model inference and NotebookLM analysis are also **not executed** by this change.

## 8. Pre-ingestion security and CI audit hardening (2026-10-19)

The QFabric v0.8 manifest and physical/AI evaluation split remain unchanged. This
maintenance pass fixed actual code-boundary risks beyond the historic, already-fixed
CI failures:

- Dataset candidate filenames cannot contain terminal control characters.
- Local integrity audits open candidate files nonblocking, then require a
  regular file via `fstat`; FIFOs/special files cannot stall a job indefinitely
  at `open` on Linux.
- Both `synthetic-baseline --output` and `audit-local-file --output`
  **refuse to overwrite** source fixtures, candidate manifest, or an existing
  report. Reports are created exclusively; choose a new filename for each run.
- Protocol JSON now refuses duplicate fields (including nested duplicate
  metadata), NaN/Infinity tokens, float overflow, oversized (>1 MiB) messages,
  and numeric overflow that formerly raised an unhandled `OverflowError`.
  Valid command-envelope JSON roundtrips remain supported.

These are *software safety guards* only; they do not establish QPU hardware
compatibility, authenticity of Zenodo-listed hashes, or scientific replication.
Tests explicitly cover refusal cases on both Python 3.11 and 3.12.
