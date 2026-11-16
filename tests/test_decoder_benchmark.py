"""Reference decoders judged by an exhaustive oracle; synthetic syndromes only."""

import json
from itertools import product
from math import comb
from pathlib import Path

import pytest

from qfabric.research.benchmark import (
    REFUSAL_NOT_SYNTHETIC,
    measure_runtime,
    parse_spec,
    run_decoder_benchmark,
)
from qfabric.research.decoders import (
    DECODERS,
    DecodingProblem,
    coset_table,
    failing_weight_counts,
    failure_probability,
    hamming_7_4,
    hamming_syndrome,
    judge_correction,
    majority_vote,
    prefix_without_vote,
    repetition_code,
)

SPEC = (Path(__file__).parent / "fixtures" / "decoder_benchmark.synthetic.json").read_bytes()


def _spec(**changes) -> bytes:
    doc = json.loads(SPEC)
    for path, value in changes.items():
        target = doc
        *parents, leaf = path.split("__")
        for part in parents:
            target = target[part]
        target[leaf] = value
    return json.dumps(doc).encode()


@pytest.mark.parametrize("distance", [3, 5, 7, 9, 11])
def test_majority_vote_is_minimum_weight_for_every_syndrome(distance: int) -> None:
    problem = repetition_code(distance)
    table = coset_table(problem)
    assert len(table) == 2 ** (distance - 1)
    for syndrome, (weight, classes) in table.items():
        correction = majority_vote(problem, syndrome)
        assert judge_correction(problem, syndrome, correction) == "agree"
        assert sum(correction) == weight and len(classes) == 1


def test_oracle_is_independent_of_the_decoders_it_judges() -> None:
    """Recompute one coset by hand: syndrome (1, 0) of the 3-bit code is {100, 011}."""
    problem = repetition_code(3)
    members = [e for e in product((0, 1), repeat=3) if problem.syndrome(e) == (1, 0)]
    assert sorted(members) == [(0, 1, 1), (1, 0, 0)]
    assert coset_table(problem)[1, 0] == (1, frozenset({(1,)}))


def test_hamming_syndrome_decoder_matches_oracle_and_textbook_failure_count() -> None:
    problem = hamming_7_4()
    for syndrome in coset_table(problem):
        assert judge_correction(problem, syndrome, hamming_syndrome(problem, syndrome)) == "agree"
    # Distance 3: every single error is corrected, every heavier error fails.
    assert failing_weight_counts(problem, hamming_syndrome) == tuple(
        comb(7, w) if w >= 2 else 0 for w in range(8)
    )


def test_negative_control_is_caught_by_the_logical_class_check() -> None:
    problem = repetition_code(5)
    verdicts = [
        judge_correction(problem, s, prefix_without_vote(problem, s)) for s in coset_table(problem)
    ]
    # It always reproduces the syndrome, so a syndrome-only check would pass it.
    assert "invalid" not in verdicts and verdicts.count("disagree") == 5
    # Exactly the errors with bit 0 flipped fail, so P(fail) = p.
    assert failure_probability(failing_weight_counts(problem, prefix_without_vote), 0.125) == 0.125


def test_adversarial_decoder_outputs_are_classified_invalid() -> None:
    problem = repetition_code(3)
    for bad in ((0, 0, 0), (1, 1), (1, 0, 2), [1, 0, 0], (True, False, False), "100", None):
        assert judge_correction(problem, (1, 0), bad) == "invalid"
    for bad_syndrome in ((1,), (1, 0, 0), (1, 2), [1, 0]):
        with pytest.raises(ValueError):
            majority_vote(problem, bad_syndrome)


def test_ambiguous_minimum_weight_is_reported_not_guessed() -> None:
    # Two-bit repetition code: syndrome 1 has two weight-1 explanations in different classes.
    problem = DecodingProblem("rep2", ((1, 1),), ((1, 0),))
    assert coset_table(problem)[1,] == (1, frozenset({(0,), (1,)}))
    assert judge_correction(problem, (1,), (1, 0)) == "ambiguous"


def test_failure_probability_is_exact_rational_arithmetic() -> None:
    counts = failing_weight_counts(repetition_code(3), majority_vote)
    assert counts == (0, 0, 3, 1)
    assert failure_probability(counts, 0.5) == 0.5
    assert failure_probability(counts, 0.25) == 3 * 0.25 ** 2 * 0.75 + 0.25 ** 3  # dyadic: exact


@pytest.mark.parametrize("bad", [2, 4, 13, 3.0, True])
def test_code_constructors_refuse_unsupported_sizes(bad) -> None:
    with pytest.raises(ValueError):
        repetition_code(bad)


def test_benchmark_report_is_deterministic_and_labelled_synthetic() -> None:
    report = run_decoder_benchmark(SPEC)
    assert report == run_decoder_benchmark(SPEC)
    assert report["comparisonTests"] == "software_correctness"
    assert report["dataProvenance"] == "synthetic"
    for flag in ("measuredSyndromeDataUsed", "hardwareExecuted", "publishedResultReproduced"):
        assert report[flag] is False
    good, control = report["summary"]
    assert good["decoder"] == "majority_vote" and good["oracleAgreementFraction"] == 1.0
    assert control["oracleAgreementFraction"] < 0.7
    assert all(row["closedFormMatchesEnumeration"] for row in report["results"])
    # Integer content is pinned so sampler, seed derivation or ordering cannot drift silently.
    assert [p["failures"] for p in report["results"][0]["points"]] == [
        2, 24, 99, 425, 864, 1654, 2058, 2595,
    ]
    assert [row["oracle"]["disagree"] for row in report["results"]] == [0, 0, 0, 1, 5, 22]


def test_monte_carlo_intervals_are_consistent_with_exact_values() -> None:
    report = run_decoder_benchmark(SPEC)
    for row in report["summary"]:
        # Nominal 95% intervals: a miss is expected sometimes, many misses are a bug.
        assert row["intervalMisses"] <= 3
        assert row["intervalMissesExpectedAtNominalCoverage"] == pytest.approx(1.2)
    for result in report["results"]:
        for point in result["points"]:
            assert point["closedFormFailureProbability"] == point["exactFailureProbability"]


def test_failure_regions_are_read_from_exact_values() -> None:
    good, control = run_decoder_benchmark(SPEC)["summary"]
    # Majority voting stops helping exactly at p >= 1/2.
    assert good["failureRegions"]["noBenefitFromLargestCode"] == [0.5, 0.6]
    assert {r["probability"] for r in good["failureRegions"]["noBenefitOverUnencoded"]} == {0.5, 0.6}
    # The broken decoder never beats an unencoded bit, at any p or size.
    assert len(control["failureRegions"]["noBenefitOverUnencoded"]) == 3 * 8


def test_zero_failure_cells_are_marked_as_upper_bounds_only() -> None:
    report = run_decoder_benchmark(_spec(
        code__sizes=[11], noise__probabilities=[0.001], decoders=["majority_vote"],
        sampling__shots=200,
    ))
    point = report["results"][0]["points"][0]
    assert point["failures"] == 0 and point["wilsonLower"] == 0.0
    assert point["resolution"] == "upper_bound_only_zero_failures"
    assert point["intervalCoversExact"] is True


def test_measured_or_unlabelled_syndrome_data_is_refused() -> None:
    for kind in ("measured", "measured_syndromes", "simulated", "caune_2024", None):
        with pytest.raises(ValueError) as caught:
            run_decoder_benchmark(_spec(kind=kind))
        assert str(caught.value) == REFUSAL_NOT_SYNTHETIC


@pytest.mark.parametrize("changes", [
    {"schemaVersion": "qfabric-decoder-benchmark-spec/2"},
    {"benchmarkId": "DBL-1"},
    {"code__family": "surface"},
    {"code__sizes": [3, 4]},
    {"code__sizes": [3, 3]},
    {"code__sizes": []},
    {"code__sizes": [13]},
    {"noise__model": "circuit_level"},
    {"noise__probabilities": [0.1, 0.05]},
    {"noise__probabilities": [0.0, 0.1]},
    {"noise__probabilities": [1]},
    {"noise__probabilities": [0.1, 0.1]},
    {"decoders": ["hamming_syndrome"]},
    {"decoders": ["majority_vote", "majority_vote"]},
    {"decoders": ["__import__"]},
    {"decoders": []},
    {"sampling__shots": 99},
    {"sampling__shots": 200_001},
    {"sampling__shots": 4000.0},
    {"sampling__seed": -1},
    {"sampling__seed": True},
    {"sampling__confidenceLevel": 0.5},
    {"sampling__confidenceLevel": 1},
])
def test_malformed_specs_fail_closed(changes) -> None:
    with pytest.raises((ValueError, TypeError)):
        parse_spec(_spec(**changes))


def test_spec_reader_refuses_duplicate_keys_extra_fields_and_oversize() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        parse_spec(SPEC.replace(b'"kind": "synthetic_fixture"',
                                b'"kind": "measured", "kind": "synthetic_fixture"'))
    with pytest.raises(ValueError, match="exactly the documented fields"):
        parse_spec(_spec(measured=True))
    with pytest.raises(ValueError, match="maximum byte length"):
        parse_spec(SPEC + b" " * 17_000)
    with pytest.raises(ValueError, match="sampling budget"):
        parse_spec(_spec(
            code__sizes=[3, 5, 7, 9, 11], sampling__shots=200_000,
            noise__probabilities=[0.01 * i for i in range(1, 7)],
        ))


def test_runtime_measurement_is_labelled_as_host_timing_only() -> None:
    timing = measure_runtime(SPEC, repeats=2)
    assert timing["provenance"] == "measured"
    assert timing["reproducibleBitForBit"] is False
    assert timing["comparableToHardwareDecoderLatency"] is False and timing["gpuUsed"] is False
    assert len(timing["rows"]) == 6
    for row in timing["rows"]:
        assert 0 < row["bestPassNanosecondsPerDecode"] <= row["worstPassNanosecondsPerDecode"]
        assert row["peakTracedBytes"] >= 0
    assert set(timing["environment"]) == {"python", "implementation", "system", "machine"}


def test_registry_binds_each_decoder_to_one_code_family() -> None:
    assert {name: family for name, (family, _) in DECODERS.items()} == {
        "majority_vote": "repetition", "negative_control_prefix": "repetition",
        "hamming_syndrome": "hamming_7_4",
    }
    report = run_decoder_benchmark(_spec(
        code__family="hamming_7_4", code__sizes=[7], decoders=["hamming_syndrome"],
    ))
    assert report["summary"][0]["oracleAgreementFraction"] == 1.0
    assert report["results"][0]["closedFormMatchesEnumeration"] is True
