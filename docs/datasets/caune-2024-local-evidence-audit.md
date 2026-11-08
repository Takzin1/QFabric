# Caune et al. (2024): reproducible QEC latency and defect-rate evidence audit

**Primary paper (provided PDF):** Laura Caune et al., *Demonstrating real-time and low-latency quantum error correction with superconducting qubits*, arXiv:2410.05202v1 (October 2024), <https://arxiv.org/abs/2410.05202>.

**Candidate data record:** <https://zenodo.org/records/15364358>, v2. **Upstream download version, authoritative checksums, and redistribution license have not been reverified.** These files were supplied directly to this development session. File provenance currently means *verified against uploaded bytes*, not authenticated against the Zenodo record.

This new lane audits **historical author-reported hardware data**, not synthetic QICK data, not a new FPGA decoder, and not new quantum-computer measurements by QFabric.

## Three input files, no third-party raw re-distribution

| Local input | Uploaded SHA-256 | Observed format | Research mapping |
| --- | --- | --- | --- |
| `decoder_timings_each_repetition.csv` | `8f23b21a27004381734fefeef80e5326e0a67c391212fcb792950cf9b51bd324` | 300,000 rows; `rounds,cycles,time_per_round` | Original paper Fig. 3(d), 9/17/25-round execution time per round |
| `defect_rates_per_round.txt` | `c923029ef8ececd2253f5efc1fe0054f549db79bdafee0671a61af1ed474ca54` | 25 rows, Qubit 50/52/36/38 | Fig. 3(b), 25-round stability-8 defect-rate series |
| `defect_rates_per_round_stability_9.txt` | `ebe0126c80fbba48b3b7dc04b3b02c6857a4aef1963089ca3dd1593e3eb46f79` | 27 rows, anonymous rate_1..rate_4 | **Unresolved**; NOT automatically equivalent to the 9-round timing series |

The supplied PDF copy SHA-256 is
`f616a3f9e66d6365576d3deb31b6314b8d5e83442197f7583e3c8c3a027e7162`.
We do **not** copy the PDF or the original measured-rate tables to the public QFabric repository while rights are unresolved.

## What the paper actually supports

- **Paper p. 3, Fig. 2 caption:** 8-qubit stability experiment; one QEC syndrome round approximately 1.7 µs.
- **Paper p. 4 §III:** FPGA decoder operating at **156.25 MHz**; 400 MHz is verified capability, not the frequency of these recordings.
- **Paper p. 5, Fig. 3(b):** defect rates by ancilla/qubit and measurement round. Defect rates are not the same as logical error rates.
- **Paper p. 5, Fig. 3(c,d):** mean per-round decoding time below 1 µs and execution-time distributions for 9, 17 and 25 rounds. The text reports 0.44 µs at 5 rounds to 0.79 µs at 25 rounds.
- **Paper p. 6 §VI:** full feedback **response** for 9 decoding rounds is 9.6 µs, comprising 6.5 µs decoding and 3.1 µs communication/control. **Do not substitute** the timing CSV's per-round averages for end-to-end feedback latency.

The original timing CSV's `time_per_round` values satisfy, row by row:

```text
time_per_round_us = cycles / (156.25 MHz * rounds)
                  = cycles * 0.0064 us / rounds
```

A positive per-repetition mean exceeding 1 µs is **not** equivalent to backlog being observed. The file lacks time-ordered syndrome arrivals, streaming completion timestamps, and actual backlog depth.

## Independently computed descriptive statistics

Computed offline from the exact uploaded CSV. For P50/P95/P99 use nearest-rank order statistics `sorted_values[ceil(p*n)-1]`. The threshold is strictly `time_per_round > 1.0 us`.

| Rounds | Rows | Mean µs/round | Median | P95 | P99 | Fraction above 1 µs |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 9 | 100,000 | 0.483114 | 0.453689 | 0.909511 | 1.189689 | 2.969% |
| 17 | 100,000 | 0.646869 | 0.593694 | 1.284141 | 1.668894 | 13.082% |
| 25 | 100,000 | 0.796577 | 0.716288 | 1.590016 | 2.007552 | 25.749% |

**No new experimental claim:** the authors generated the observations on their hardware; QFabric independently parsed and recomputed summaries from user-uploaded copies. The 1 µs comparison is diagnostic, not a novel rate of observed QEC failures.

For the named 25-round defect-rate series, first → last:

| Ancilla | First | Last | Change (percentage points) |
| --- | ---: | ---: | ---: |
| Qubit 50 | 0.31069 | 0.33762 | +2.693 |
| Qubit 52 | 0.30659 | 0.36299 | +5.640 |
| Qubit 36 | 0.27783 | 0.32345 | +4.562 |
| Qubit 38 | 0.31922 | 0.35475 | +3.553 |

Defect aggregates have no source shot denominators/covariance in these input files. Do not infer statistical significance or independent trials. The other 27-round `stability_9` series must be studied separately until its origin and labels are resolved.

## Reproduce locally

Use QFabric's Python 3.11+ development environment, preserving all three original byte files. This CLI uses only the standard library. No network or hardware required:

```bash
python -m pip install -e ".[dev]"
python scripts/caune_dataset_audit.py \
  /path/to/decoder_timings_each_repetition.csv \
  /path/to/defect_rates_per_round.txt \
  /path/to/defect_rates_per_round_stability_9.txt \
  --output /tmp/caune2024-audit.json
ruff check .
pytest
```

The CLI checks all three **uploaded-copy SHA-256 pins**, input sizes, schema, finite values, strict sequential rounds, 156.25 MHz cycle/time identity across 300,000 rows, and 100,000 records in each 9/17/25 group. It refuses an existing output file. No raw input is embedded in the package. CI runs **synthetic parser/adversarial tests only**; CI does not contain or validate the private local measured source bytes.

## Follow-on Figure 4 feedback analysis (2026-11-08)

Four additional user-uploaded author figure CSVs for 2–9 rounds, Supplementary Gamma fits and the 13-point T1 reference are handled in [caune-2024-feedback-evidence.md](caune-2024-feedback-evidence.md). This is a **different-day** feedback-experiment source from the 9/17/25-round throughput dataset. Do not pair source records across those experiments. Raw files and licensing remain outside the public repository.

## Next research gates

1. Verify exact Zenodo record/version, published file-specific checksums and license against these pinned SHA-256 hashes; only then consider third-party raw data publication.
2. Resolve `defect_rates_per_round_stability_9.txt` with an original data dictionary or figure legend; **27 rows != 9 rounds**.
3. Obtain paired per-shot syndrome and decoder timing events before estimating defect-dependent causal latency or a **true streaming backlog**.
4. For hardware benchmarks, separate mean throughput, p99, measured end-to-end feedback and QEC logical-error rate. No IQ/readout or FPGA control functionality is added to QFabric.
