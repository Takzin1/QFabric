# QFabric v0.8+ — Independent Baseline & Falsifiability Layer

**Scope:** Research references and a *synthetic-only* statistical diagnostic. Source download, model fitting, physical hardware execution and replication have **not occurred**.

## Why four genuinely different baselines?

| ID | Perspective | Peer-reviewed paper / primary dataset | Threat to hypothesis / disconfirming evidence |
| --- | --- | --- | --- |
| ALT-001 | Mirror randomized benchmarking (gate layer / cross-talk) | Proctor et al., [Phys. Rev. Lett. 129, 150502 (2022)](https://doi.org/10.1103/PhysRevLett.129.150502), [Zenodo v2 record 5176787](https://zenodo.org/records/5176787) | Performance improvement absent or reversed under wider/deeper mirror circuits, simultaneous operation, or held-out circuit families |
| ALT-002 | Mid-circuit measurement + spectator qubits | Govia et al., [New J. Phys. 25, 123016 (2023)](https://doi.org/10.1088/1367-2630/ad0e19), [Zenodo record 6815663](https://zenodo.org/records/6815663) | Candidate appears beneficial on target qubit while unmeasured spectator errors worsen; measure-in-the-middle and no-intermediate-measurement control |
| ALT-003 | Independent estimation / Gate Set Tomography vs Direct RB | Rozanov, [preprint arXiv:2509.06881](https://arxiv.org/abs/2509.06881), [Zenodo 17523497](https://zenodo.org/records/17523497) | Fit improves on training subset but fails pre-separated validation; DRB and GST disagree outside specified tolerance. **Simulation-only**; `.pcl` pickle must never be deserialized from untrusted input |
| ALT-004 | Different physical technology and quantum volume | Jäger et al., [npj Quantum Inf 12, 6 (2026)](https://doi.org/10.1038/s41534-025-01164-0), [DaRUS V1 CSV data](https://doi.org/10.18419/DARUS-5322) | A claimed cross-device universal improvement disappears when tested on NV-center quantum registers or normalized for different circuit/connectivity and measurement conditions |

The last row is a deliberately different platform. Quantum volume, mirror RB, GST fit consistency, QEC logical error rate, mid-circuit measurement crosstalk and plotted CSV observables **are not equivalent metrics**. Do not average them into one score. A paper can use real quantum measurements *and* model-calculated quantities in the same archive; classify file and column contents before scientific use.

Four source leads are stored separately in [`independent_baseline_sources.json`](../../data/independent_baseline_sources.json), with exact published source URLs, file basenames, published MD5 **claims**, source origin, paper URLs, version caveats and status `not_downloaded`. The v2 mirror-RB record points to a newer record; **do not switch versions silently**. No raw SHA-256 has been independently checked, and file-level redistribution rights remain unaudited.

A fifth useful control: [Google's QEC below-threshold paper](https://doi.org/10.1038/s41586-024-08449-y) with [112.5 GB dataset, Zenodo 13273331](https://zenodo.org/records/13273331). It documents rare correlated error bursts and was **corrected April 28, 2026**. It is an *important challenge to simple i.i.d. assumptions*, not a downloaded or checked data baseline. Its original work and correction should both be consulted before numerical reproduction.

## Machine-readable falsification contract

The [synthetic test fixture](../../tests/fixtures/falsification.synthetic.json) supplies per-study **customizable** fields:

- `sourceBaselineId`: citation ID of an independent baseline lead. This identifies the *intended research perspective*, not evidence that the source's experiment was reproduced.
- `claim`: human-readable falsifiable hypothesis fixed *before* looking at results.
- `metric: binary_outcome_probability` and `direction: lower_is_better | higher_is_better`: only independently observed binary events can enter the **synthetic** rate estimator.
- `minimumImprovement`: pre-declared absolute difference between arm event proportions (0 to 1), never a percent relative reduction.
- `confidenceLevel`: configurable strictly between 0.80 and 0.999.
- `minimumShotsPerArm`: explicitly bounded minimum of 30–1,000,000.
- `samplingAssumption: independent_bernoulli`, `noiseModel: synthetic_independent_only`: a compulsory fail-closed assumption. Do not claim paired, clustered, drifting, burst-error or repeated-measures experimental validity.
- `control` and `candidate`: {shots, events}; synthetic fixture only. Real outcomes are not accepted by this schema.
- `sensitivityThresholds`: up to 10 additional thresholds labeled **exploratory only**, never treated as a post-hoc confirmatory claim.
- `analysisPlan: pre_declared_single_primary_threshold`: forbids confirmation via data-driven threshold optimization.

### Decision logic

A simultaneous confidence interval for the difference is formed by Bonferroni-corrected Wilson score intervals for **two independent binomial arms**: each arm has nominal coverage `1 - alpha/2`, so the difference interval has at least `1 - alpha` simultaneous coverage under the assumptions.

If `direction=lower_is_better`, improvement = `p_control - p_candidate`. For higher-is-better, reverse the subtraction.

- `consistent_with_improvement`: conservative difference CI lower bound is **strictly greater** than the primary minimum improvement.
- `falsifies_minimum_improvement`: conservative CI upper bound is **strictly lower** than the primary minimum improvement.
- `inconclusive`: neither side; **not** an acceptance or rejection of physical validity.

These labels are conditional frequentist diagnostics, **not** an acceptance of the research paper, a validated gate-fidelity measurement, or proof of a quantum advantage. Sensitivity scan labels can disagree and are **exploratory**; there is no familywise adjustment across those scanned thresholds. Actual QEC shot correlations invalidate the independent-binomial sampling model.

### Run offline

```bash
python scripts/quantum_dataset_baseline.py validate-alternative-sources data/independent_baseline_sources.json
python scripts/quantum_dataset_baseline.py synthetic-falsification tests/fixtures/falsification.synthetic.json --sources data/independent_baseline_sources.json --output counterexample.synthetic.report.json
pytest tests/test_falsification.py -q
```

The fixture contains three **invented** count comparisons, deliberately illustrating: one improvement-consistent result, one explicit **counterexample**, and one inconclusive result. These counts are **not** from Proctor, Govia, Rozanov or Jäger. The JSON report hashes the exact fixture and source-catalog bytes so result changes can be traced. It always reports `measurementVerified=false`, `scientificReplication=false`, `hardwareExecuted=false`.

For peer-reviewed numerical reproduction, a future, separate real-data adapter must enforce exact record version, file license, SHA-256 of actual bytes, valid unit mapping, matched noise conditions, stratification and experimental design, full circuit/shot metadata, equipment calibration, estimator definition, independent holdout, pre-registered claim and appropriate uncertainty (e.g., block/cluster bootstrap when time-correlated). No automatic inference or comparison across unlike observables.

## Publication and safety limits

- These four entries are **source leads**, not imported numerical arrays. First verify each relevant figure CSV / archive inventory without running external code.
- Dataset/record webpage licenses and author-supplied checksums are *source claims*. No file-level license and local SHA-256 audit has been performed.
- Never `pickle.load` an external `.pcl` dataset; use a separately sandboxed/verified conversion path outside the default QFabric process.
- No raw quantum device data were used. No physical quantum processor was contacted. Synthetic intervals should **never** be represented as measured performance.
