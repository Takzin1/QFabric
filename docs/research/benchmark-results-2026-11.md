# Benchmark results — 2026-11-16

All values below were produced in one session on one host and can be
regenerated with the commands shown. Nothing here is a measurement of a quantum
device or of a hardware decoder.

**Host.** Linux x86-64, Intel Xeon @ 2.30 GHz, 4 cores. Python 3.12.3 for the
tables; 3.11 and 3.13 where stated.

## 1. Decoder benchmark `DBL-001` (tests software correctness)

**Input.** `tests/fixtures/decoder_benchmark.synthetic.json`,
SHA-256 `a91c62a723bab094f1919ce1d31a2eecda9afe60f3ac5dd8f57ed1b36e4341bf`.
Repetition codes of 3, 5 and 7 bits; i.i.d. bit flips at eight probabilities;
4,000 shots per cell; seed 20261116; 95 % Wilson intervals.

**Procedure.**

```bash
python scripts/quantum_dataset_baseline.py decoder-benchmark \
  tests/fixtures/decoder_benchmark.synthetic.json --output report.json
```

**Output.** `resultDigest`
`b571e8bbb24164b2aa4b64180e4c31ed1acda1bc9dad2038f4d11323d1b7c611`, identical
on Python 3.11, 3.12 and 3.13 on this host.

### Oracle agreement (every syndrome)

| Decoder | 3 bits | 5 bits | 7 bits | Agreement |
| --- | --- | --- | --- | --- |
| `majority_vote` | 4 / 4 | 16 / 16 | 64 / 64 | 1.0 |
| `negative_control_prefix` (deliberately wrong) | 3 / 4 | 11 / 16 | 42 / 64 | 0.656 |

No ambiguous or invalid corrections. The negative control is detected, which is
the point of including it.

### Closed form against enumeration

Failing errors by weight, `majority_vote`: `[0,0,3,1]`, `[0,0,0,10,5,1]`,
`[0,0,0,0,35,21,7,1]`. These equal the binomial counts C(n, w) for w > n/2
exactly, for all six decoder/code pairs.

### Monte Carlo against exact (`majority_vote`)

| Bits | p | Exact failure probability | Failures / 4,000 | 95 % Wilson interval | Covers exact |
| --- | --- | --- | --- | --- | --- |
| 3 | 0.01 | 0.000298 | 2 | 0.000137 – 0.00182 | yes |
| 3 | 0.05 | 0.00725 | 24 | 0.00404 – 0.00891 | yes |
| 3 | 0.1 | 0.028 | 99 | 0.0204 – 0.0300 | yes |
| 3 | 0.2 | 0.104 | 425 | 0.0971 – 0.116 | yes |
| 3 | 0.3 | 0.216 | 864 | 0.204 – 0.229 | yes |
| 3 | 0.45 | 0.42525 | 1654 | 0.398 – 0.429 | yes |
| 3 | 0.5 | 0.5 | 2058 | 0.499 – 0.530 | yes |
| 3 | 0.6 | 0.648 | 2595 | 0.634 – 0.663 | yes |
| 5 | 0.01 | 9.85 × 10⁻⁶ | 0 | 0 – 0.00096 | yes (upper bound only) |
| 5 | 0.05 | 0.00116 | 6 | 0.00069 – 0.00327 | yes |
| 5 | 0.1 | 0.00856 | 37 | 0.00672 – 0.0127 | yes |
| 5 | 0.2 | 0.05792 | 230 | 0.0507 – 0.0652 | yes |
| 5 | 0.3 | 0.16308 | 674 | 0.157 – 0.180 | yes |
| 5 | 0.45 | 0.40687 | 1642 | 0.395 – 0.426 | yes |
| 5 | 0.5 | 0.5 | 2025 | 0.491 – 0.522 | yes |
| 5 | 0.6 | 0.68256 | 2706 | 0.662 – 0.691 | yes |
| 7 | 0.01 | 3.42 × 10⁻⁷ | 0 | 0 – 0.00096 | yes (upper bound only) |
| 7 | 0.05 | 0.000194 | 1 | 0.0000441 – 0.00142 | yes |
| 7 | 0.1 | 0.002728 | 11 | 0.00154 – 0.00492 | yes |
| 7 | 0.2 | 0.033344 | 141 | 0.0300 – 0.0414 | yes |
| 7 | 0.3 | 0.126036 | 506 | 0.117 – 0.137 | yes |
| 7 | 0.45 | 0.391712 | 1583 | 0.381 – 0.411 | yes |
| 7 | 0.5 | 0.5 | 1963 | 0.475 – 0.506 | yes |
| 7 | 0.6 | 0.710208 | 2795 | 0.684 – 0.713 | yes |

Across all 48 cells (both decoders) one interval missed: the negative control
at 5 bits, p = 0.05 (231 failures, interval 0.0509 – 0.0654, exact 0.05). At a
nominal 95 % level about 2.4 misses in 48 are expected, so one is unremarkable.

### Failure regions

- **Statistically unresolved.** At p = 0.01 the 5- and 7-bit cells saw zero
  failures in 4,000 shots. The data bound the rate below about 10⁻³ and cannot
  distinguish 10⁻⁵ from 10⁻⁷. Resolving them needs on the order of 1/p_fail shots.
- **No benefit from the code.** From exact values, `majority_vote` fails at
  least as often as an unencoded bit, and the 7-bit code is no better than the
  3-bit code, at p = 0.5 and p = 0.6 — i.e. exactly at and beyond p = 1/2.
- **Negative control.** Its failure probability equals p at every size: it
  never beats an unencoded bit.

## 2. Preregistered experiment and replay

Manifest `tests/fixtures/experiment_manifest.synthetic.json`
(SHA-256 `6d16025efe4b139ac8c43d920d079bca22fd53b8cf8a71132dc46e4b90374936`).
Hypothesis: majority vote is minimum-weight for every syndrome. Endpoint:
`oracleAgreementFraction` of `majority_vote` ≥ 1.0.

```bash
B=scripts/quantum_dataset_baseline.py; F=tests/fixtures
python $B experiment-review $F/experiment_manifest.synthetic.json \
  --reviewer-label "your label" --decision approve --output review.json
python $B experiment-run $F/experiment_manifest.synthetic.json \
  --spec $F/decoder_benchmark.synthetic.json --review review.json --output result.json
python $B experiment-replay $F/experiment_manifest.synthetic.json result.json \
  --spec $F/decoder_benchmark.synthetic.json --review review.json
```

| Step | Observed |
| --- | --- |
| Run | `status: completed`, endpoint `met` (observed 1.0), exit 0 |
| Replay, same Python | `identical: true`, exit 0 |
| Replay of a 3.12 result under 3.11 | `identical: true` after the fix below |
| Result edited (`observed` → 0.5) then replayed | `identical: false`, exit 3 |
| Same manifest with subject `negative_control_prefix` | endpoint `not_met`, exit 2 |
| Model-originated manifest, no review | refused, exit 1, nothing written |

The result digest depends on the review file, so yours will differ from any
quoted one unless the reviewer label matches.

**A reproducibility defect this caught.** The first implementation summed
floating-point terms with `sum()`. Python 3.12 changed `sum()` to compensated
summation, so a result written under 3.12 failed to replay under 3.11. Exact
probabilities are now computed in rational arithmetic and rounded once.

## 3. Runtime and memory (host measurements, not reproducible bit-for-bit)

**Procedure.** `time.perf_counter` around the whole call, best and worst of the
stated number of runs; `tracemalloc` peak for one further run.

| Workload | Runs | Best | Worst | Peak traced memory |
| --- | --- | --- | --- | --- |
| `run_decoder_benchmark` on `DBL-001` (192,000 shots) | 5 | 0.165 s | 0.168 s | 86,858 bytes |
| `summarize_latency`, 300,000 synthetic samples | 3 | 0.154 s | 0.159 s | not measured |
| `quantile_rank_interval(2,000,000, 0.999, 0.95)` | 1 | under 1 ms | — | not measured |

Per-decode timings from `decoder-runtime` (best pass, pure Python):
`majority_vote` 584 ns (3 bits), 730 ns (5), 858 ns (7);
`negative_control_prefix` 478, 574, 692 ns. Peak traced allocation 464 bytes in
every row. These are properties of this interpreter on this host. They are not
comparable to an FPGA decoder's latency.

## 4. Profiling and the decision not to optimise

`cProfile` of `run_decoder_benchmark`: 0.62 s of 0.64 s (under the profiler) is
the sampler, dominated by drawing 1.15 million random bits. `cProfile` of
`summarize_latency`: `math.fsum` and one `sorted` call. `QickPlanAdapter.compile`
is quadratic in pulses per generator: 0.58 s at 8,000 commands, which is about
the largest envelope the 1 MiB limit admits.

Nothing measured exceeds 0.6 s on its largest admissible input, so no
optimisation was implemented. No GPU path was added; there is no workload here
that would justify one.

## 5. Regression evidence

| Suite | Baseline `838cfef` | This branch |
| --- | --- | --- |
| `ruff check .` | pass | pass |
| `pytest`, Python 3.11 | 418 passed | 666 passed |
| `pytest`, Python 3.12 | 418 passed | 666 passed |
| Bridge generate + `--verify` smoke | pass | pass |
| `gari_reference_check.py` smoke | pass | pass |

All 418 baseline tests still pass unmodified. Run locally in fresh virtualenvs;
GitHub Actions results are reported on the pull request itself.
