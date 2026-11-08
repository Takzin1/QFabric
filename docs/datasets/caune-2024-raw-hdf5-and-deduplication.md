# Caune et al. (2024): deduplication and fast-feedback raw HDF5

**Source:** Laura Caune et al., *Demonstrating real-time and low-latency quantum error correction with superconducting qubits* (arXiv:2410.05202v1, 2024), <https://arxiv.org/abs/2410.05202>. These files are **user-supplied**. The original file-specific Zenodo checksums, source release version, rights and redistribution permission remain unverified.

This extends the [30万行のデコーダ処理時間の解析](caune-2024-local-evidence-audit.md)、[Figure 4 / T1 analysis](caune-2024-feedback-evidence.md) and [LEP decoder comparisons](caune-2024-lep-decoder-comparison.md). **None of the 3 new raw files is committed** to the public repo.

## Redundancy decision before importing

| Source | SHA-256 (exact user-supplied bytes) | Duplicate assessment | Actual usage |
| --- | --- | --- | --- |
| `mean_decoding_time.txt` | `0e163c3b8c7c80140333f4a1832396248466c10d150fa08da39a6d58b5d1bf30` | **Partially redundant:** 9, 17, 25-round means were already recomputed from the 300,000-row CSV, to 6 decimal places | Validate those **3** overlapping means, add only **9** other rounds' means plus author-reported error values |
| `lep_mwpm_stability_9.txt` | `d5d8b1d9ee0937e8b154ee40a681705d127fd7ad709df8784f0813a1b453e001` | **Different experimental series:** 5,7,…,27 rounds; LEP about 0.39–0.40, unlike stability-8 source | Register 12 LEP estimates and their `std` column, with *unresolved original figure identity*. Do **not** pool with stability-8 or infer a reset comparison |
| `fast_feedback_raw_data.h5` | `dd2a3d48e86ea81094b44439fb58a3d9788757e26799bd4ee7497eb94798ed08` | **New provenance depth:** contains shot-level author-experiment records; not a duplicate of the published Figure 4 summaries | Validate HDF5 structure, qubit readout arrays, 8 round groups of 1000 records each, separate 10k-shot reference acquisitions, and fit 13-point T1 from hard-measurement proportions |

The mean-time summary's 9/17/25 **value** agrees with prior `audit_decoder_timings` re-analysis, but the mean-time table's original **`err` column** was not provided by that previous dataset report and is preserved as an author-supplied error field with meaning still to verify. Its 3 overlaps are **not** counted as three independent experiments.

The 12-entry `lep_mwpm_stability_9.txt` has `lep,std` columns, not `lep,err`, and is **not** the existing `defect_rates_per_round_stability_9.txt`. They concern different observables and cannot be automatically paired without confirming the dataset dictionary / experimental sessions.

## HDF5 source inspection (new data, not derivative figure summaries)

The **5.4 MB** user-uploaded HDF5 file contains:

- `circuit_0/result` through `circuit_7/result`: rounds **2 through 9**. Each has **1,000 author shots**, `decoder_shot_results` with **8 or 9 integer FPGA register values** per shot, `time` with 1,000 positive integers, `hard_measurements` (bits), and `soft_measurements` (complex IQ samples) for qubits **36, 37, 38, 43, 45, 50, 51, 52**.
- `reference_data/measurement_fidelity/ones` and `zeros`: **10,000** reference hard-measurement shots each. From those hard bits alone: measured bit-1 frequency **0.9466** for prepared `1`, **0.0328** for prepared `0`; equal-prior *descriptive* readout correctness **0.9569**. Do not mistake this for the average fidelity across the whole processor.
- `reference_data/delays/delay_0..delay_12`: **13 delay settings**, 0 to **9.6 µs** in 0.8 µs steps, with **10,000** measured hard bits each. The new code recomputes binomial standard errors under an explicitly labeled independent-shot approximation and fits `A exp(-t/T1)+B` by independently profiling weighted least squares.
- `session_data/qpu_name` reports **Ankaa-2**. The HDF5 source is historical hardware data supplied by its authors; QFabric did not connect to it or acquire new measurements.

**Independent preview of local raw bits** (derived via Python/h5py inspection, not a public repository copy): weighted fit of the 13 delayed 10k-shot reference bit fractions gives **T1 ≈ 13.19 µs**, consistent with the paper's `13 ± 1 µs`. This may differ slightly from fit to rounded, separately supplied figure-point estimates (≈13.06 µs) because the inputs/weights differ. Both are source-data re-analyses, not new physical experiments.

**Critical time-unit gate:** HDF5 `result/time` has positive integers but **no explicit unit attribute**. We refuse to silently convert those to nanoseconds, FPGA clock cycles or µs, even though separate Figure 4 values are reported in µs. The auditor reports raw integer mean/P95/P99 in **unresolved native units**, and `derivedLatencyMicroseconds=null`. Register names are only checked structurally; their physical meanings/clock rates must be verified before interpreting conditional feedback or performing syndrome decoding.

**Never load/execute** embedded `stim_circuits/.../stim_circuit_0` or other object-valued program datasets. The audit explicitly accesses only fixed known numeric hard/soft measurement locations; unknown/external HDF5 links are rejected, and raw IQ arrays are checked only for finite numbers and compatible shapes. It **does not** publish, return or log per-shot records.

## Reproduce from three original files locally

```bash
python -m pip install -e ".[dev,research-hdf5]"
python scripts/caune_new_sources_audit.py /local/folder/containing/three/files \
  --output /tmp/caune-new-sources-audit.json
ruff check .
pytest
```

The offline JSON contains only newly derived numeric summaries, source-byte hashes, explicit duplicate classifications, hard-bit means, and scientific limitations. Existing report files are never overwritten. The optional `research-hdf5` extra installs `h5py`; **QFabric's public core remains free of h5py and vendor hardware SDK imports**. CI installs this extra to test generated *synthetic* HDF5 files and malformed/externally linked adversarial cases. The authors' raw HDF5 itself is **not in CI**.

## Follow-up: Appendix E2/E3, two-shot postmeasurement calibration (2026-11-08)

The source HDF5 also contains an additional **non-duplicate** reference:
`reference_data/double_measurement/{zeros,ones}/result/hard_measurements/50`.
Each preparation has **10,000 separate pairs** of sequential Qubit-50 hard
measurements. The original paper Supplementary Appendix E, Fig. 4(f),
Eqs. **(E2)–(E3)** uses a **500 ns** ringdown and the readout confusion
matrix together with `m(t)=A exp(-t/T1)+B` to infer the state immediately
after the first measurement. The paper does **not** name HDF5 FPGA
registers `DASR`, `DSR` or `MGUEVCNTR` with sufficient precision to
assign an end-to-end microsecond latency or decoder corrections here.

The independent audit added to `caune_hdf5.py` preserves both
preparation-specific pair count matrices before pooling equal-sized
`zeros` and `ones` references. Row = first measured bit, column = second
measured bit; pooled **author raw-source** counts:

| First measured | Second 0 | Second 1 | \(P(M_2=1 \mid M_1)\) |
| ---: | ---: | ---: | ---: |
| 0 | 9,750 | 424 | 0.041675 |
| 1 | 1,426 | 8,400 | 0.854875 |

Using `P(M=1|S=0)=0.0328` from the separate 10k prepared-zero
reference and **the raw-shot T1 fit** `A≈0.86579, T1≈13.189 µs,
B≈0.08269`, the paper's Eq. E2–E3 gives:

```text
m(0.5 us) = A * exp(-0.5/T1) + B ≈ 0.916271

P(S_1'=1|M_1'=j) =
  [ P(M_2'=1|M_1'=j) - P(M_2'=1|S_1'=0) ] /
  [ m(0.5 us) - P(M_2'=1|S_1'=0) ]
```

The resulting estimates are **≈0.010045 for first measured bit 0**
and **≈0.930506 for first measured bit 1**. They are conditional
model-based postmeasurement state fractions, not measured quantum-state
tomography, decoder LEP, or independent hardware results. The preparation
groups are pooled with an explicitly declared balanced-prior convention,
and **uncertainty propagation is not performed**. Nonphysical inferred
probabilities, mismatched preparation labels, bad shapes, nonbinary data
or HDF5 external links cause an error rather than a silent correction.

**What remains blocked:** Figure 4(b) feedback-latency reproduction
cannot be derived from the unlabeled HDF5 `result/time` integers alone,
and the raw `DASR`/other register bitfield meanings are not established
by the provided paper. The HDF5 auditor explicitly reports
`hdf5TimingClockUnitVerified=false`,
`fpgaRegisterBitfieldSemanticsVerified=false` and
`fastFeedbackLogicalCorrectionRecovered=false`.
Do not present estimates from this calibration as a claim that QFabric
has implemented a real-time quantum decoder.

## Scientific holdout gates

1. Authenticate Zenodo's exact HDF5 version, original published checksum, data dictionary and redistribution license before publishing any raw measurements.
2. Resolve HDF5 `time` physical unit and FPGA register semantics against the authors' processing code or release documentation; do not infer from similarly named Figure 4 fields.
3. Establish whether the stability-9 LEP and 27-round defect-rate tables share an experimental run before interpreting association; this is **not** stability-8.
4. For new scientific performance claims, obtain independently executable decoding code, matched per-shot syndromes and corrections, timestamps, hardware/deadline configuration, and repeat across hardware sessions. **No HDF5 inspection alone demonstrates improved algorithm or hardware performance.**
