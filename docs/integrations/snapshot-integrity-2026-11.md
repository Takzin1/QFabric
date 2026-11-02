# Snapshot integrity hardening (November 2026)

**Status:** offline structural validation; *not* scientific validation.

The CrystalTwinAI → QFabric interchange remains `crystaltwin-qfabric-snapshot/1`.
The same fail-closed semantic checks run in both the QFabric research proposal
gate and the plan-only demonstration bridge:

- Educational input ranges: 20–90 °C; 0.1–0.6 g/mL; stirring 0–1000 rpm;
  cooling 0.05–2 °C/min; impurity 0–5%.
- `timeSteps` is 10–200 for new interactive runs; precisely **2** remains
  supported for the existing, labelled, synthetic historical fixture.
- Trajectory step numbers are contiguous, starting at one; temperatures and
  concentrations do not increase, yields do not decrease, and growth is nonnegative.
- Reported final yield and mean growth must agree with the trajectory within
  numeric tolerance; scores and event counts obey educational ranges.
- Version, provenance labels, field sets, finite numbers, file-size limits,
  duplicate JSON keys and exact byte-bound SHA-256 continue to be checked at
  the existing entrypoints.

**Nonclaims:** A self-consistent synthetic report can still be fictional.
These checks do not verify authorship, experimental observations, crystallization
physics, QICK device behavior, or CUDA execution. No input reaches hardware.
Do not silently convert this structural gate into a model-validity claim.

Run `python -m pytest tests/test_snapshot_integrity.py` and the complete CI
before merging; retain the documented negative tests for both entrypoints.

## Next scientific milestones

1. Version-pin an experimental source record (DOI, exact units, raw SHA-256,
   acquisition conditions, explicit permission to redistribute) independently
   of any model.
2. Compare model predictions with held-out *measured* trajectories only after
   materials, solvent and boundary-condition comparability gates pass.
3. Implement predeclared paired/cluster-aware statistics and falsification tests
   rather than applying independent-binomial assumptions to QEC time series.
4. Build a signed/reviewed evidence manifest if actual operator identity and
   authorization become necessary; SHA-256 alone is *not* a signature.
5. Run GPU and QICK software compatibility tests with recorded hardware/software
   versions; distinguish runtime signature binding from real RFSoC operation.
