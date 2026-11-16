# Caune 2024: tail-percentile uncertainty, comparability and HDF5 source identity

**Status (2026-11-16):** stacked on PR #26 (`research/caune-zenodo-v2-evidence-20261110`,
head `6882edd`). Verified on **synthetic fixtures only**. The author files were
**not** re-analysed with this change: this session's network policy blocks
`zenodo.org`, and no author data is stored in the repository. Run the existing
`Caune Zenodo v2 source authentication` workflow on this branch to obtain
real-data values; none are quoted here.

## 1. HDF5 source identity (closes the PR #25 review item)

`audit_fast_feedback_hdf5` used to hash the file through one open and then let
`h5py` open the same path again. A file replaced between the two opens would be
parsed under the SHA-256 of different bytes, and `Path.is_file()` followed
symbolic links.

`_read_verified` now opens the path once with `O_NOFOLLOW`, checks on the
descriptor that it is a regular file within the 12 MiB limit, reads it, hashes
those bytes and hands the same bytes to `h5py.File(io.BytesIO(raw))`. The path
is never opened a second time.

| Test (`tests/test_caune_hdf5.py`) | What it shows |
| --- | --- |
| `test_parsed_bytes_are_the_hashed_bytes_even_if_the_file_is_swapped` | The file is overwritten at the moment `h5py` opens; the report is unchanged and `h5py` never receives a path. |
| `test_symlink_directory_and_fifo_sources_are_refused` | Symbolic link, FIFO, directory, missing and empty files are refused with `ValueError`. |

The hard-link-only traversal that refuses HDF5 external and soft links is unchanged.

## 2. Tail percentiles now carry intervals

`audit_decoder_timings` already reported mean, median, p95, p99 and the count
above 1 µs per group. Each group gains an `uncertainty` object produced by
`qfabric.research.latency.summarize_latency`:

- p50, p90, p95, p99 and p99.9 with a distribution-free order-statistic
  interval (`TRC-001` in `data/research_traceability.json`);
- a Wilson interval for the fraction of repetitions above 1 µs per round;
- a normal-approximation interval for the mean;
- the lag-1 autocorrelation in file order with a white-noise band.

The existing fields and their values are unchanged; the new point estimates use
the same nearest-rank rule and a test asserts they are equal.

What the intervals mean, and do not mean:

- They assume the repetitions are independent and identically distributed.
  The lag-1 diagnostic flags a violation; it cannot prove independence.
- The file's row order is used for that diagnostic. The source does not state
  that row order is acquisition order.
- The quantity is still *decoding time per round averaged over one repetition*.
  It is not a per-round latency and not a backlog probability. The existing
  caveat in the report stands.
- A percentile the sample cannot bound is reported as unresolved. With 3,000
  repetitions the 99.9th percentile has no 95 % upper bound, and the test
  fixture demonstrates exactly that.

## 3. LEP comparisons are declared before they are formed

`audit_caune_lep_bundle` now attaches a comparability verdict to each of its
two existing comparisons, from `qfabric.research.comparability`:

| Comparison | Verdict |
| --- | --- |
| FPGA real-time vs offline soft-information MWPM (Fig. 3a) | comparable; tests a scientific hypothesis; **descriptive only** (figure aggregates without covariance, session undeclared) |
| With vs without ancilla resets (Suppl. Fig. 6 vs Fig. 3a) | comparable; **descriptive only** for the same reasons |
| FPGA no-reset vs offline with-reset | **refused**: two conditions differ, only one declared |
| Any stability-8 series vs the stability-9 table | **refused**: different experiment |

This replaces nothing: the earlier boolean flags
(`causalResetImprovementEstablished`, `directComparisonToStability8Permitted`,
…) remain in the reports.

## 4. Measured cost (same host, same synthetic input, same method)

Input: a synthetic CSV of 300,000 rows in the author schema (5,875,346 bytes,
seeded generator, not author data). Method: `time.perf_counter` around
`audit_decoder_timings(raw, enforce_pin=False)`, three runs, Python 3.12.3,
Linux x86-64.

| | Best of 3 | Worst of 3 |
| --- | --- | --- |
| Before (PR #26 head) | 0.569 s | 0.620 s |
| After (with `uncertainty`) | 0.702 s | 0.750 s |

`cProfile` attributes most of the time to `csv.DictReader` and per-row
validation. No optimisation was made: the audit runs once per dataset and a
faster reader would have to give up `DictReader`'s column checks for well under
a second of saving.

## 5. Still open

- Dataset licence and redistribution rights (unchanged gate from PR #26).
- HDF5 `time` unit and FPGA register semantics (unchanged).
- No syndrome-level interpretation of the HDF5 hard bits is validated, so the
  decoder benchmark does not accept this data. It accepts synthetic syndromes only.
- Real-data values for the new intervals: not yet produced (see Status).
