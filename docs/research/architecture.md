# QFabric research architecture

This document describes the six research layers, what each is allowed to claim,
and where its code and tests live. It complements
[`docs/architecture.md`](../architecture.md), which covers the control protocol.

## Layers

| | Layer | Code | State |
| --- | --- | --- | --- |
| A | Versioned experiment protocol | `protocol.py`, `models.py`, `spec/` | Existing; unchanged |
| B | Hardware-agnostic planner | `profiles/qick.py`, `profiles/qick_readout.py` | Existing; plan-only, unchanged |
| C | QEC evidence and datasets | `dataset_baseline.py`, `gari_*.py`, `source_intake.py`; `caune_*.py` on the PR #25/#26 stack; `research/latency.py`, `research/comparability.py` | Extended |
| D | Classical decoder benchmark laboratory | `research/decoders.py`, `research/benchmark.py` | New, first vertical slice |
| E | Statistical falsification and verification | `falsification.py`, `research/stats.py` | Extended |
| F | Human-reviewed research orchestrator | `orchestration.py` | Extended with experiment manifests |

~~~text
            untrusted JSON (manifest, spec, proposal, snapshot)
                              |
              strict bounded reader, exact field sets
                              |
        F  orchestration: review gate -> allowlisted OFFLINE analysis
                              |
          +-------------------+--------------------+
          |                   |                    |
   D  decoder lab      C  evidence audits    E  statistics
   (synthetic only)    (hashed source bytes) (stated assumptions)
          |                   |                    |
          +---------- structured result + digest --+
                              |
                    replay: recompute and compare

   A/B  protocol and QICK planning are separate; nothing above calls them,
        and no analysis in F's allowlist can reach hardware.
~~~

Vendor-specific logic stays in `profiles/`. `qfabric.research` imports only the
standard library and existing QFabric helpers.

## Provenance model

Four labels, defined in `qfabric/research/__init__.py`, never merged:

| Label | Meaning | Example |
| --- | --- | --- |
| `measured` | A physical experiment produced it | Author-reported FPGA cycle counts; this host's decode timings |
| `simulated` | A physics model produced it | Author simulation summaries (GARI CSV) |
| `synthetic` | A fixture with no physical content | Seeded bit-flip syndromes; test snapshots |
| `inferred` | Derived from other data through a model or fit | A fitted T1; a Gamma-fit mean |

`measured` says who made the measurement only in context: reports that analyse
author data keep their existing flags (`qfabricMeasurementsPerformed: false`).
A SHA-256 shows two byte strings are equal. It does not show who wrote them.

## What a comparison may claim

Every comparison states exactly one of three purposes
(`research/comparability.py`):

| `tests` | When | What a pass means |
| --- | --- | --- |
| `software_correctness` | synthetic vs synthetic | The code does what its specification says |
| `scientific_hypothesis` | measured vs measured, or simulated vs simulated | Evidence about the declared varied condition |
| `experimental_validity` | measured vs simulated | Evidence about whether the model describes the experiment |

`assess_comparison` **refuses** when quantity, unit, aggregation level or
experiment differ, when provenance classes cannot be paired, when a condition
differs that was not declared as the varied one, or when the declared one does
not differ. When sessions differ or the data are figure aggregates, it allows
the comparison as `descriptive_only`.

## Layer D: decoder benchmark laboratory

**Input.** A `qfabric-decoder-benchmark-spec/1` document: code family and
sizes, i.i.d. bit-flip probabilities, decoder names, shots, seed, confidence
level. `kind` must be `synthetic_fixture`.

**Interface.** A decoder is `f(problem, syndrome) -> correction`. A
`DecodingProblem` is a parity-check matrix and a matrix of logical observables.
Decoders are registered by name against one code family; a spec cannot name
arbitrary code.

**Three independent checks per decoder.**

1. *Oracle.* `coset_table` enumerates all 2ⁿ errors and records, per syndrome,
   the minimum weight and the logical classes that reach it. A correction is
   `agree`, `disagree`, `ambiguous` (the minimum is genuinely tied) or `invalid`
   (wrong shape, or it does not reproduce the syndrome).
2. *Closed form.* The number of failing errors of each weight is compared, as
   integers, with a textbook formula.
3. *Monte Carlo.* Seeded samples; the Wilson interval is compared with the
   exact failure probability.

**Negative control.** `negative_control_prefix` is deliberately wrong and
always reproduces the syndrome. A harness that only checked syndromes would
pass it. The benchmark must, and does, flag it.

**Output.** `qfabric-decoder-benchmark-report/1`: deterministic, with a
`resultDigest`. Host timings are a separate, explicitly non-reproducible
document (`qfabric-decoder-runtime-measurement/1`).

**Scope.** Classical codes of at most 12 bits under bit-flip noise. It is a
software-correctness harness. It is not a surface-code decoder, and its results
say nothing about a hardware decoder or a published experiment.

## Layer E: statistics

| Function | Method | Assumption |
| --- | --- | --- |
| `quantile_rank_interval` | Order-statistic interval from binomial ranks | i.i.d.; any distribution; conservative under ties |
| `wilson_interval` | Wilson score | Independent Bernoulli trials; nominal coverage |
| `mean_interval` | Normal approximation | i.i.d., n ≥ 30, finite variance |
| `lag1_autocorrelation` | Sample autocorrelation | Diagnostic only: can flag dependence, cannot prove independence |

When a sample cannot bound a tail, the bound is `null` with a reason. Intervals
are marginal, not simultaneous; reports count how many missed and how many
misses the nominal level predicts.

## Layer F: orchestration

Two flows share the strict reader and the review rule.

*Proposals* (existing, unchanged): snapshot → `qfabric-research-proposal/1` →
assessment → self-attested review → manual simulation input.

*Experiment manifests* (new): `qfabric-experiment-manifest/1` names a
hypothesis, a preregistered endpoint (metric, subject, minimum), hashed inputs
with provenance labels, and one analysis from an allowlist.

| Rule | Enforcement |
| --- | --- |
| Only `offline_analysis_only` | Any other `requestedAction` is refused at parse |
| Model-originated manifests need a human | `run_experiment` raises without an approving review whose content is recomputed from the manifest bytes |
| The endpoint cannot move after the run | It is inside the hashed manifest |
| Failures are evidence | A wrong input or analysis error returns `status: failed` with a `stage`; it replays identically |
| A manifest cannot relabel provenance | Declared input provenance must equal the analysis's own label |
| Replay | `replay_experiment` recomputes and compares with JSON-typed equality |

Reviews are self-attested. `reviewerAuthenticated` is always `false`.

## Schemas introduced

| Schema | Producer |
| --- | --- |
| `qfabric-decoder-benchmark-spec/1` | hand-written input |
| `qfabric-decoder-benchmark-report/1` | `run_decoder_benchmark` |
| `qfabric-decoder-runtime-measurement/1` | `measure_runtime` |
| `qfabric-latency-summary/1` | `summarize_latency` |
| `qfabric-experiment-manifest/1` | hand-written or model-written input |
| `qfabric-experiment-review/1` | `make_manifest_review` |
| `qfabric-experiment-result/1` | `run_experiment` |
| `qfabric-research-traceability/1` | `data/research_traceability.json` |

All are new names. No existing schema changed, so there is nothing to migrate.

## Security boundaries

- No network access, subprocess, dynamic import or file write inside `src/qfabric/research` or the manifest code.
- Inputs are bounded: 16 KiB specs and manifests, 2 MiB results, 12-bit codes, 200,000 shots per cell, 5,000,000 in total, 2,000,000 latency samples.
- Every JSON reader rejects duplicate keys, `NaN`/`Infinity`, overflowing numbers and unknown fields.
- CLI output is written with exclusive create; evidence is never overwritten.
- GPU: none of this uses one. The only GPU path in the repository remains the optional, labelled CuPy branch of the bridge, with CPU as the default.

## Unresolved research limitations

1. No syndrome-level measured dataset is authenticated, so layer D has never seen real syndromes.
2. The reference decoders are classical and tiny. Matching or union-find decoding of a surface code, with a detector error model, is not implemented.
3. Noise is i.i.d. bit flips. No circuit-level, correlated, leakage or measurement-error model.
4. Interval methods assume independence. Real shot sequences drift; the lag-1 diagnostic is a weak detector.
5. Wilson intervals are nominal. No multiplicity correction is applied across benchmark cells.
6. Reviews are self-attested text, not signatures.
7. Report digests were observed identical on Python 3.11, 3.12 and 3.13 on one Linux x86-64 host. Other platforms' `log` could differ in the last bit of a Wilson bound; the exact probabilities and all integer content cannot.
8. Caune licence, HDF5 time unit and FPGA register semantics remain open on the PR #25/#26 stack.

## Roadmap

| Stage | Work | Gate before starting |
| --- | --- | --- |
| 1 | Land #25 → #26 → stacked Caune PR; dispatch the Zenodo workflow to produce real-data tail intervals | Dataset licence review |
| 2 | Detector-error-model input for layer D; a union-find reference decoder checked against the oracle on distance-3 codes | A synthetic DEM fixture with a hand-derived answer |
| 3 | Authenticated syndrome intake: hash-pinned source, schema, units, a validated mapping from readout bits to detectors | A source whose syndrome semantics are documented by its authors |
| 4 | Dependence-aware intervals (block bootstrap with recorded seed), simultaneous bands | A measured sequence with documented acquisition order |
| 5 | Second analysis on the manifest allowlist (`latency_summary`), signed reviews | A decision on the signing mechanism |
| 6 | Cross-repository contract test in CI for `ctqf-research-bundle/1` once #24 and CrystalTwinAI #52 merge | Both merged |
