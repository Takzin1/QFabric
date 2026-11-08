# Caune 2024 — Figure 4 full-feedback timing, SI Gamma and T1 evidence

**Source**: Laura Caune et al., *Demonstrating real-time and low-latency quantum error correction with superconducting qubits*, arXiv:2410.05202v1 (2024), <https://arxiv.org/abs/2410.05202>. User-provided original PDF (22 pages) and four user-uploaded figure-data CSVs.

**What changed**: An offline, read-only audit of end-to-end feedback timing, author's **KDE curve** and **Gamma fit**, and independently computed weighted T1 reference fit. This is a follow-up to the independent decoder/defect analysis in [caune-2024-local-evidence-audit.md](caune-2024-local-evidence-audit.md).

## Source and SHA-256 inventory

| Local file | SHA-256 of **user-supplied bytes** | Rows | Paper mapping |
| --- | --- | ---: | --- |
| `fig4b_decoding_response_time.csv` | `00155d0e94fb799679476ca759d71edd2c3a21cc6967a80d20244e3c150ea2a4` | 8 | Main Fig. 4(b), rounds 2–9 |
| `figS4c_feedback_response_time_probability_density_data.csv` | `48e5e19a74316d34d3a4819d5e88707e90a0a863e16e74e6f8bf682eec4fc61a` | 380 | Supplementary Fig. 4(c), Gaussian KDE **evaluated points** |
| `figS4c_feedback_response_time_probability_density_fit_parameters.csv` | `f56ae6a00dc8adbcfd344fed8a1f5a6105df1eb91bdc2202330eb80ed4ac295f` | 8 | Supplementary Fig. 4(c), Gamma `k,theta` from authors' fit |
| `figS4d_t1_time_fitting.csv` | `94c135e6e6d5eb40cc078becc7bfe866aa2e2a72cda7bad53162891df16d117e` | 13 | Supplementary Fig. 4(d), excited state population vs delay with `+/-` uncertainty |

These are **copies submitted by the user**. Their byte hashes are not a check against publisher- or Zenodo-signed authoritative checksums. Dataset record, version, file-level license and republication rights remain unverified. The PDFs and original CSVs are **not committed** to public GitHub.

## Conventions grounded in the original article

- Main paper §VI (p. 6) reports **9.6 µs full response** for 9 QEC rounds, broken down as **6.5 µs decoder**, **3.1 µs communication and control**.
- Despite the source field name `control_system_logic`, its value for 9 rounds is **9556.256**. Based on the author's paper Fig. 4(b) and 9.6 µs aggregate, the auditor interprets the field as **the full clock-measured response in ns**, not overhead alone. `decoding_time` is also interpreted in **ns**. This is an explicit source interpretation, not silently renamed input data.
- Qubit-derived `delay_measured_by_qubit` is expressed in **µs**. The `*_std` columns are retained as provided; do not assume they are independent sample-level variances. The paper's Fig. 4(b) caption describes the qubit delay error bars as standard errors of the mean.
- Supplementary Appendix E (PDF supplementary pages 4–8), Fig. 4(c,d), Eq. (E1): `m(t)=A exp(-t/T1)+B`, reported `T1 = 13 +/- 1 µs`. Eq. (E10) defines Gamma shape `k` and scale `theta`. Eq. (E13) gives **`T1*k*log(1+theta/T1)`** as an *effective expectation* after the qubit-T1 estimator; this is not an additional physical measurement.
- The KDE ordinate is a **density**, not a raw probability per time point or a row of per-shot data. Its finite plotting window is not assumed to integrate to exactly one.

## Independently recomputed published figure-level summaries

| Rounds | FPGA total (µs) | FPGA decoder (µs) | Non-decoder difference (µs) | Authors' Gamma mean kθ (µs) |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 3.200704 | 0.655008 | 2.545696 | 3.033017 |
| 3 | 4.099680 | 1.508454 | 2.591226 | 4.051523 |
| 4 | 4.835296 | 2.212870 | 2.622426 | 4.780865 |
| 5 | 5.676320 | 3.005389 | 2.670931 | 5.655982 |
| 6 | 6.689664 | 3.954637 | 2.735027 | 6.759757 |
| 7 | 7.692096 | 4.742323 | 2.949773 | 7.652568 |
| 8 | 8.610208 | 5.575974 | 3.034234 | 8.610141 |
| 9 | **9.556256** | **6.522253** | **3.034003** | **9.481193** |

For round 9 and paper's stated `T1=13 µs`, Eq. (E13) evaluates to approximately **9.361420 µs**, which differs from the Gamma mean (9.481193 µs) by **0.119773 µs** (about **1.26%**). This is a *model-based bias calculation*, not measured improvement in hardware performance.

A separate weighted least-squares nonlinear fit of the 13 reference points with their provided `+/-` uncertainties gave:

- `A ≈ 0.859571`, `T1 ≈ 13.058728 µs`, `B ≈ 0.088959`;
- weighted residual χ² ≈ **12.0456**, degrees of freedom **10** (the raw 13 aggregate points minus 3 fitted parameters).
- These are consistent with original authors' rounded `A=0.87 +/- 0.05; T1=(13 +/- 1) µs; B=0.08 +/- 0.05` (Eq. E1). We do **not** reconstruct their uncertainty propagation or hidden original sample counts.

The KDE 2-round series has **30** recorded grid values, and the other seven series each have **50** (total 380). The 2-round trapezoidal area over its recorded plotting window is approximately **0.895**, illustrating why a truncated KDE grid must not automatically be treated as a normalized discrete probability distribution.

## Independent Python 3.11+ reproduction

Keep all four original source CSVs on your local machine. The parser uses Python standard library, numerical guards, exact file SHA-256 pins and no network access:

```bash
python -m pip install -e ".[dev]"
python scripts/caune_feedback_audit.py \
  /local/fig4b_decoding_response_time.csv \
  /local/figS4c_feedback_response_time_probability_density_data.csv \
  /local/figS4c_feedback_response_time_probability_density_fit_parameters.csv \
  /local/figS4d_t1_time_fitting.csv \
  --output /tmp/caune-feedback-audit.json
ruff check .
pytest
```

The JSON is **derived statistics, provenance and limits only**. No original CSV rows or publisher PDF are embedded. Existing output files are protected from overwrite.

## Audit trust boundaries and next experiments

1. This verifies **author's aggregated figure data** against uploaded-byte hashes. It does not independently replay the original hardware experiment or fit the author Gamma law from per-shot clock times (the supplied `k,theta` already come fitted).
2. Full response, decoder execution, estimated physical-qubit response, Gamma-model mean and T1-based effective estimate are **different observables/estimates**. The four CSVs are not paired per-shot records, so regression of response latency on defect counts or causal attribution is unsupported.
3. No measured backlog trace, quantum fault-tolerance threshold, FPGA placement/routing, new device access, or verified QICK physical compatibility is established by these figures.
4. Next controlled step: obtain upstream checksums/data dictionary, inspect full shot/timestamp logs (if available under acceptable license), and predeclare latency-tail / streaming backlog criteria before evaluating a proposed decoder.

## Scientific cross-check

The supplementary PDF itself explicitly notes that feedback-experiment results were obtained on a **different day** than the logical-error/throughput data (§E). Do not pool the old `decoder_timings_each_repetition.csv` distribution with the new Fig. 4(b) latency points as if they were matched runs.
