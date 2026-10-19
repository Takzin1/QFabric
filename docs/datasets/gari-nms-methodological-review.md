# Methodological review: GARI-NMS (Maan et al., Nature Communications 2026)

**Independent software-methods review, not a journal refereeing decision.**
Primary source: *Decoding correlated errors in quantum LDPC codes*, Arshpreet Singh Maan, Francisco Miguel Garcia Herrero, Alexandru Paler and Valentin Savin, Nature Communications **17**, 3965 (2026), DOI [10.1038/s41467-026-70556-3](https://doi.org/10.1038/s41467-026-70556-3). Source artifact inspected: user-provided 13-page publisher PDF. Published accepted March 2, 2026. GitHub reproduction repository: [astra-decoders/gari-nms](https://github.com/astra-decoders/gari-nms), pinned source commit `6380d52e76d8c9cb0b4eedf3e8d2429b24cef78d`, repository LICENSE **Apache-2.0**.

## Distinguish four levels of evidence

1. **Proven algebra:** Equations (1)–(6), page 3, transform a correlated detector error model into an augmented GF(2) system while preserving the syndrome problem, *provided* every Y-column matches a unique single-detector-type column in both `DX` and `DZ`. The QFabric original **toy reference** checks all 64 error vectors for a 6-variable example and reports 4-cycles before/after. This is not a quantum simulation result.
2. **Authors' simulations:** figures 1, 4, 5, 7, tables 1–2, using BB codes [[72,12,6]], [[90,8,10]], [[144,12,12]], Stim circuits, different depolarizing/SI1000 noise conditions. Paper claims `(6.70 ± 1.93) × 10⁻⁹` per-round LER for [[144,12,12]] at physical `p=10⁻³`. QFabric has **not reproduced** that numerical figure.
3. **Authors' published summary CSV:** we include the **exact upstream file** `data/final/BB_final_google_si1000_data.csv`, fetched from the pinned code repository at Git blob SHA-1 `f9cadb313eb60a71fb1c9fc893c4b9d288178502`. The QFabric parser compares Git-blob bytes and independently recomputes the article's formula (7) from the **authors' existing** shots/errors/rounds. These counts remain author-reported **simulation** outputs, not fresh Monte Carlo or physical observations.
4. **FPGA latency estimates:** the paper implemented **DX, DZ and bottom processing units independently**, giving per-iteration estimates ~2.9 µs and `1.13 × 2900 / 12 = 273 ns` per round for [[144,12,12]]. The 99.992% four-iteration statistic derives from Fig. 6 and a time budget. It is **not** a demonstration of an integrated, independently timed complete hardware decoder, and not a quantum computer experiment. See paper pp. 8–9.

## Methodological strengths

- Identifies the Y-induced 4-cycle problem and derives an explicit invertible variable-lifting formulation instead of merely tuning decoder hyperparameters.
- Includes two detector types, correlated Pauli X/Y/Z errors, physical-gate-level Stim circuits and several BB code distances.
- Specifies NMS normalization `0.96875` / `0.9921875`, up to 400 iterations, randomized serial/layered schedule and parallel ensembles (24 or 48 for different noise models), permitting structured ablation.
- Includes BPOSD, XYZ-Relay-BP and Tesseract baselines with 99% error bars and a documented hardware design rationale.
- Makes author source code, Stim circuits and figure-input CSV available under a repo-level Apache-2.0 LICENSE.

## Review concerns / falsification program

**R1 — Comparison fairness and computational budget.** The paper notes its baseline XYZ-Relay-BP implementation uses **301** sequential decoders, whereas the earlier reported results used **601**. Separately, BPOSD and GARI use different tuning/scheduling/iteration budgets (BPOSD order-zero / up to 30 vs GARI up to 400). Register a matched-config comparison with identical circuits, noise model, seeds, trial counts, and measured wall-clock/CPU/GPU cores. Do not interpret simulation `seconds` as FPGA nanoseconds. Source: PDF p. 7.

**R2 — Rare failures and intervals.** At LER around 10⁻⁹, credible empirical error bars require immense numbers of trials. Audit confidence interval construction, stopping rules, parameter tuning data reuse and the number of observed failures. Paper specifies at least ~100 failures for most plots and ~40 for some references; the ultra-low-error comparison and figure-level tail statistics require a separately audited trial-count log. Source: PDF p. 7.

**R3 — Ensemble ablation.** Compare single GARI-NMS, 24-way and 48-way ensembles, same error patterns and matched latency envelopes. The paper already reports ensemble benefit varying by distance: for distance-6, a single decoder is adequate; for d=10/12 ensembles matter. Hypothesis can fail if added ensemble hardware/cost overwhelms gain or if gains vanish on held-out circuits.

**R4 — Correlated noise robustness.** Re-run against a predeclared sweep of independent, circuit-level correlated, SI1000, burst and drift models. The original paper does **not** establish all those models. Do not use independent-binomial Wilson inference on clustered/same-seed paired failures without a suitable statistic.

**R5 — Observable and detection semantics.** The implementation primarily examines **Z-memory experiments** and checks Z-type syndrome for early stopping. Passing that check is not equivalent to protecting both logical X and Z observables in arbitrary computation. Paper p. 5 explicitly discusses increased iterations for simultaneous checks. Register an alternate X-memory/dual-observable experiment and possible counterexamples.

**R6 — Full-device latency external validity.** Measure post-placement-and-routing integrated FPGA design, clock-domain crossings, memory contention, per-round p99.99 and worst-case backlog. The **273 ns figure derives from per-block timing plus average iteration count**; real integrated timing must be considered separately. Include FPGA family/clock constraints and hardware resource use.

**R7 — Reproducible tooling.** Authors' README says a cleaned-up release is forthcoming, Python 3.11 needed, and asks for `pip install ldpc stim sinter`; code imports additional modules including `pymatching`, `numpy`, uses a compiled C shared library via `ctypes` and repository contains a `.so`. Version pinning and environment isolation are required for scientific reproduction. QFabric deliberately **does not load their compiled `.so`**, build their Makefile, execute arbitrary scripts, or deserialize untrusted pickle.

## Implemented in QFabric

- `src/qfabric/gari_reference.py`: bounded independent synthetic GF(2) reference for equations (1)–(6), original and augmented matrix construction, four-cycle counts, BPT axis and numerically stable equation (7) `LER_round=(1-(1-2*LER)^(1/r))/2`.
- `src/qfabric/gari_evidence.py`: read-only CSV parser enforcing a pinned Git blob SHA-1, strict column schema, no unverified hardware or independent replication claims, and line-wise calculations of per-round rates from author-supplied counts.
- `data/reference/gari_nms_si1000_upstream.csv`: source-author SI1000 data, copied verbatim from the pinned GitHub commit; preserve original code attribution and repo license. **This is the first actual external numeric simulation-summary file under this research lane** and must never be misidentified as QPU measurements.
- `tests/test_gari_reference.py`: algebraic equivalence for all 2^6 error vectors, negative malformed-matrix tests, correlation, Figure 1 BPT points and author-record tampering.
- `scripts/gari_reference_check.py`: offline smoke for these two separate evidence gates.

## Explicit non-claims

**We did not implement or execute GARI-NMS decoding**, compute the paper's 6.7e-9 LER from newly simulated errors, run GARI authors' C/OpenMP code, benchmark PyMatching/Stim externally, implement FPGA logic, confirm 273 ns on real hardware or conduct a fresh independent peer review for the journal.

Future proposal: use a separately isolated, dependency-pinned trusted runner to run the author's code *and* independent PyMatching/Stim baselines on identical circuit files with predeclared matched evaluation rules. Preserve actual sample-level failures, seed/memory/timing and environmental metadata; track paired effects, heterogeneity, confidence intervals and effect-size sensitivity. Until then, distinguish **review**, **algebraic validation**, **source-data recalculation** and **full empirical replication**.
