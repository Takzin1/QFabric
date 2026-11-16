"""Interval estimates and latency summaries: exactness, coverage and refusals."""

import math
import random
from math import comb

import pytest

from qfabric.research.latency import QUANTILES, summarize_latency
from qfabric.research.stats import (
    lag1_autocorrelation,
    mean_interval,
    quantile_rank_interval,
    wilson_interval,
)


def _brute_force_ranks(n: int, q: float, confidence: float) -> tuple[int | None, int | None]:
    """Independent reference: full binomial table with math.comb, no recurrence."""
    tail = (1 - confidence) / 2
    mass = [comb(n, k) * q ** k * (1 - q) ** (n - k) for k in range(n + 1)]
    lower = upper = None
    total = 0.0
    for k in range(n + 1):
        total += mass[k]
        if total > tail:
            break
        lower = k + 1
    total = 0.0
    for k in range(n, -1, -1):
        total += mass[k]
        if total > tail:
            break
        upper = k
    return lower, upper


@pytest.mark.parametrize("n", [1, 2, 5, 10, 37, 100, 500])
@pytest.mark.parametrize("q", [0.01, 0.5, 0.9, 0.99, 0.999])
@pytest.mark.parametrize("confidence", [0.8, 0.95, 0.999])
def test_quantile_ranks_match_independent_binomial_table(n, q, confidence) -> None:
    assert quantile_rank_interval(n, q, confidence) == _brute_force_ranks(n, q, confidence)


def test_quantile_ranks_stay_exact_where_the_binomial_underflows() -> None:
    # (1-q)**n underflows to zero here; the windowed recurrence must not.
    lower, upper = quantile_rank_interval(2_000_000, 0.999, 0.95)
    assert lower < math.ceil(0.999 * 2_000_000) < upper
    assert upper - lower < 400


def test_unresolvable_tail_is_reported_not_extrapolated() -> None:
    # 100 samples carry no upper bound on the 99.9th percentile at 95%.
    assert quantile_rank_interval(100, 0.999, 0.95)[1] is None
    summary = summarize_latency(
        [float(v) for v in range(100)], quantity="q", unit="us", provenance="synthetic",
        ordered=False,
    )
    tail = summary["quantiles"][-1]
    assert tail["probability"] == 0.999 and tail["resolved"] is False
    assert tail["upper"] is None and "upper side" in tail["unresolvedReason"]
    assert summary["independenceDiagnostic"] == "not_assessed_sample_order_unknown"


def test_quantile_interval_coverage_on_a_skewed_distribution() -> None:
    """Scientific-method check: nominal 95% intervals must cover in >= ~95% of trials."""
    rng = random.Random(20261116)
    truth = -math.log(1 - 0.9)  # 90th percentile of Exp(1)
    lower, upper = quantile_rank_interval(200, 0.9, 0.95)
    trials = 600
    covered = 0
    for _ in range(trials):
        sample = sorted(rng.expovariate(1.0) for _ in range(200))
        covered += sample[lower - 1] <= truth <= sample[upper - 1]
    assert covered / trials >= 0.93  # 0.95 minus ~2 binomial standard errors


def test_latency_summary_is_ordered_consistent_and_labelled() -> None:
    rng = random.Random(7)
    values = [rng.gammavariate(2.0, 0.25) for _ in range(5000)]
    summary = summarize_latency(
        values, quantity="decode time per round", unit="microseconds",
        provenance="synthetic", ordered=True, thresholds=(1.0,),
    )
    assert summary["provenance"] == "synthetic" and summary["samples"] == 5000
    assert [row["probability"] for row in summary["quantiles"]] == list(QUANTILES)
    for row in summary["quantiles"]:
        assert row["resolved"] and row["lower"] <= row["estimate"] <= row["upper"]
    estimates = [row["estimate"] for row in summary["quantiles"]]
    assert estimates == sorted(estimates) and estimates[-1] <= summary["maximum"]
    over = summary["exceedance"][0]
    assert over["count"] == sum(v > 1.0 for v in values)
    assert over["wilsonLower"] <= over["fraction"] <= over["wilsonUpper"]
    assert summary["mean"]["lower"] < 0.5 < summary["mean"]["upper"]  # Gamma(2, 0.25) mean
    assert summary["independenceDiagnostic"] == "lag1_within_white_noise_band"


def test_serial_correlation_is_flagged_instead_of_silently_trusted() -> None:
    drifting = [float(i // 50) for i in range(2000)]  # slow drift, strongly autocorrelated
    summary = summarize_latency(
        drifting, quantity="q", unit="us", provenance="synthetic", ordered=True,
    )
    assert summary["lag1Autocorrelation"] > 0.9
    assert summary["independenceDiagnostic"].endswith("intervals_likely_too_narrow")
    assert lag1_autocorrelation([1.0] * 10) is None


@pytest.mark.parametrize("kwargs", [
    {"values": [1.0]},
    {"values": [1.0, float("nan")]},
    {"values": [1.0, float("inf")]},
    {"values": [1.0, -0.5]},
    {"values": [1.0, True]},
    {"values": [1.0, "2.0"]},
    {"provenance": "verified"},
    {"provenance": "measured_and_simulated"},
    {"confidence": 0.5},
    {"confidence": 1},
    {"unit": ""},
    {"thresholds": (float("nan"),)},
    {"thresholds": tuple(range(9))},
])
def test_latency_refuses_malformed_samples_and_unknown_provenance(kwargs) -> None:
    args = {
        "values": [1.0, 2.0, 3.0], "quantity": "q", "unit": "us",
        "provenance": "synthetic", "ordered": False, **kwargs,
    }
    values = args.pop("values")
    with pytest.raises((ValueError, TypeError)):
        summarize_latency(values, **args)


def test_mean_interval_needs_thirty_samples_and_wilson_checks_counts() -> None:
    assert mean_interval([1.0] * 29, 0.95) is None
    mean, low, high = mean_interval([float(i % 2) for i in range(400)], 0.95)
    assert mean == 0.5 and low < 0.5 < high and high - low < 0.11
    low, high = wilson_interval(0, 1000, 0.95)
    assert low == 0.0 and 0.003 < high < 0.004  # zero events still bounds the rate
    for events, trials in ((-1, 10), (11, 10), (0, 0), (True, 10), (1.0, 10)):
        with pytest.raises(ValueError):
            wilson_interval(events, trials, 0.95)
