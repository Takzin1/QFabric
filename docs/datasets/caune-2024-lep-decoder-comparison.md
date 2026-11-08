# Caune et al. (2024): five author LEP tables, decoder comparisons, reset controls

**Original publication:** Laura Caune et al., *Demonstrating real-time and low-latency quantum error correction with superconducting qubits*, arXiv:2410.05202v1 (2024), <https://arxiv.org/abs/2410.05202>. Paper PDF and five original figure-table TXT files supplied by the user.

This is an **independent audit of authors' reported figure-level estimates**, not an independent experiment, newly performed decoder test, raw shot reprocessing or proof that a quantum error correction protocol is practically fault-tolerant.

## Source/figure map and pinned copies

| Supplied local filename | SHA-256 of user-uploaded bytes | Paper reference | Row set |
| --- | --- | --- | --- |
| `lep_fpga.txt` | `9e3893c60ef1302d958d5752762089480beae65e5aed0f522af489b8917e7c36` | Main Fig. 3(a), real-time FPGA | 5, 7, …, 25 (11) |
| `lep_mwpm.txt` | `2243153c8564f5441fcfe1cefcd40ba2bd51c3c75f3841f70f92a5e63539aea7` | Main Fig. 3(a), offline MWPM/hard readout | 5, 7, …, 25 (11) |
| `lep_belief_matching.txt` | `3c28afe0f1970aa829089f1543dcf22babbe1c6cb4731835cc87c006b52c28b4` | Main Fig. 3(a), offline belief matching/hard readout | 5, 7, …, 25 (11) |
| `lep_mwpm_soft_info_pairwise_correlation_graph.txt` | `106be5ff47bcb3e7474932461b2886371a7cdf2ea60783100856ba7777fb85f8` | Main Fig. 3(a), offline MWPM soft information + pairwise-correlation graph | 5, 7, …, 25 (11) |
| `lep_mwpm_soft_info_pairwise_correlation_graph_with_resets.txt` | `95dba7ac221519828d942c203f51d2e0b7a150b81fed337c9c4bd357a4c66164` | Supplementary Fig. 6 and Appendix F, offline MWPM soft + correlation graph **with unconditional DDROP resets** | 7, 11, 15, 19, 23 (5) |

All sources provide **whitespace-indexed aggregated `lep` (logical error probability) and `err` values**, NOT raw binary logical outcomes or decoded syndromes. The original bytes are intentionally **not redistributed in this public GitHub PR**; the repository contains only code, user-upload SHA-256 fingerprints, derived comparison examples and synthetic tests. No original Zenodo file hash or licensing claim has been independently confirmed.

## Paper-controlled scientific boundaries

- Main §IV and Fig. 3(a), p. 4–5: the experiment uses 8 qubits with 5–25 decoding rounds, 100,000 repetitions per condition as described by the authors. Fig. 3(a) compares a **hardware-executed real-time FPGA** decoder against **offline postprocessed** software MWPM, belief matching and soft-information MWPM/correlation-graph decoding. Four lines **do not** mean four algorithms implemented on FPGA.
- The Methods §VIII.D, p. 11: belief matching runs using PyMatching2/BeliefMatching; authors report no notable improvement for their chosen experiment because the omission of the middle stabilizer removes hyperedges. We do not run or recreate those decoders.
- Main Fig. 3(a) caption: `err` denotes author-supplied error bars described as standard errors of mean. The supplied tables cannot establish a **joint** covariance of algorithm outputs or a properly paired uncertainty for their differences.
- Supplementary Appendix F, pp. S8–S10 and Fig. 6: authors used unconditional **DDROP resets** but explicitly **did not evaluate resets with the real-time FPGA decoder**. The fifth series is a separate offline analysis; the paper's reset procedure includes a 1.5 µs applied pulse. We do not create or send any RF/reset control signals.
- Supplementary Fig. 6 caption describes error bars as standard deviations of the mean values. This is not silently assumed identical to all main-figure error-bar definitions. In addition, the uploaded no-reset Fig. 3(a) and reset Fig. 6 tables lack per-shot pairing and independently authenticated run/session IDs. Their numerical contrast is descriptive, not a causal matched estimate.

## Descriptive, source-audited results

The analysis keeps the full 11×4 and 5×1 original table values only in the **local** generated JSON report. Representative recomputed contrasts:

| Rounds | FPGA real-time LEP | Offline soft/correlation LEP | Absolute difference | Relative decrease vs FPGA |
| ---: | ---: | ---: | ---: | ---: |
| 5 | 28.1360% | 26.8180% | 1.3180 percentage points | 4.68% |
| 25 | 20.5253% | 17.6230% | 2.9023 percentage points | 14.14% |

At **25 rounds**, baseline hard-information MWPM is **20.0128%** and belief matching **19.9658%**, versus FPGA **20.5253%** and offline soft/correlation **17.6230%**. The four series are from the authors' Fig. 3(a), not QFabric experimental executions.

For the **five only** overlapping nominal round indices in the reset table:

| Rounds | Soft/correlation no-reset LEP (main Fig. 3a copy) | With resets (Suppl. Fig. 6 copy) | Difference |
| ---: | ---: | ---: | ---: |
| 7 | 24.422% | 23.203% | 1.219 percentage points |
| 11 | 22.190% | 20.092% | 2.098 percentage points |
| 15 | 20.752% | 18.511% | 2.241 percentage points |
| 19 | 19.434% | 16.858% | 2.576 percentage points |
| 23 | 19.390% | 15.901% | 3.489 percentage points |

This comparison should be reported as **descriptive differences between figures and conditions**. A reset-specific causal estimate requires confirming that corresponding source conditions/sessions and other controls match. Figure 6 is the appropriate original source for the authors' *internal* reset/no-reset experiment comparison; we must not silently declare the uploaded Fig. 3(a) no-reset table to be the paired original Figure 6 baseline.

The LEP curves are not strictly monotone: at **23 rounds** there is a reversal versus 21 rounds in all main-figure series. The auditor accepts actual non-monotonic data; it neither smooths nor extrapolates.

## Local reproducibility with zero raw-data redistribution

Python 3.11+ with only standard-library parsing. Put the five exact user-supplied TXT files together in one local directory:

```bash
python -m pip install -e ".[dev]"
python scripts/caune_lep_audit.py /path/to/five-author-tables \
  --output /tmp/qfabric-caune-lep-audit.json
ruff check .
pytest
```

The reader enforces strict filenames, original-byte SHA-256 fingerprints, 4 KiB input limits, whitespace-header format, positive finite `err`, bounded finite `lep`, expected round indices, increasing unique rounds, and coverage of all five files. It emits a no-overwrite JSON including the author figure-level values, annotated differences, and explicit **no hardware/no causal significance** indicators.

CI **does not** possess third-party measured source files. It tests generated synthetic structures and adversarial mutations (NaN, duplicate rounds, skipped rows, wrong filename, mismatched hash, wrong reset round set). Passing CI establishes *software parser/test behavior*, not independent QEC hardware reproduction.

## Next methodological advance

1. Independently authenticate file-specific Zenodo checksums/version and license, preserving provenance through a source registry.
2. Confirm Figure 6 no-reset source file and run IDs before claiming a matched reset experiment; obtain source-wise shot counts, error-bar definitions and paired shot outcomes.
3. Only after acquiring proper per-shot correctness/syndrome logs, assess the covariance of decoder outputs on the **same shots**, confidence intervals for paired differences, and sensitivity to rounds/hardware drift.
4. A future separately reviewed experimental study could benchmark decoder throughput vs logical error probability under matched noise/power and operation settings. **No physical quantum execution, DDROP implementation, or FPGA modification** is included here.

Related audits: [decoder timing and defects](caune-2024-local-evidence-audit.md) and [full feedback/T1 figures](caune-2024-feedback-evidence.md).
