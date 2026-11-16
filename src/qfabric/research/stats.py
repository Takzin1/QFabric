"""Interval estimates with the sampling assumption each one depends on.

Standard library only. Every interval here is conditional on independent,
identically distributed samples; correlated or drifting shots make them too
narrow, and nothing in this module can detect that from summary counts alone.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import pairwise
from statistics import NormalDist, fmean

from qfabric.falsification import _wilson

MIN_SAMPLES_FOR_NORMAL_MEAN = 30


def check_confidence(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, float) or not 0.8 <= value <= 0.999:
        raise ValueError("confidence level must be a float within [0.8, 0.999]")
    return value


def wilson_interval(events: int, trials: int, confidence: float) -> tuple[float, float]:
    """Two-sided Wilson score interval for a binomial proportion (nominal coverage)."""
    if any(type(v) is not int for v in (events, trials)) or not 0 <= events <= trials or not trials:
        raise ValueError("require integer 0 <= events <= trials and trials > 0")
    z = NormalDist().inv_cdf(1 - (1 - check_confidence(confidence)) / 2)
    low, high = _wilson(events, trials, z)
    # The bounds at the edges are exactly 0 and 1; do not let rounding claim otherwise.
    return (0.0 if events == 0 else low), (1.0 if events == trials else high)


def _binomial_window(n: int, q: float) -> tuple[int, list[float]]:
    """Binomial(n, q) probabilities for every k whose mass is not negligible.

    Built outwards from the mode with the exact term ratio, so no term is
    computed as a difference of large numbers. Returns (first k, probabilities).
    """
    mode = min(n, int((n + 1) * q))
    peak = math.exp(
        math.lgamma(n + 1) - math.lgamma(mode + 1) - math.lgamma(n - mode + 1)
        + mode * math.log(q) + (n - mode) * math.log1p(-q)
    )
    odds = q / (1 - q)
    below: list[float] = []
    term, k = peak, mode
    while k > 0 and term > 1e-300:
        term *= k / ((n - k + 1) * odds)
        k -= 1
        below.append(term)
    above: list[float] = []
    term, k = peak, mode
    while k < n and term > 1e-300:
        term *= (n - k) * odds / (k + 1)
        k += 1
        above.append(term)
    return mode - len(below), [*reversed(below), peak, *above]


def quantile_rank_interval(n: int, q: float, confidence: float) -> tuple[int | None, int | None]:
    """Order-statistic ranks (lower, upper), 1-indexed, bracketing the q-quantile.

    With B ~ Binomial(n, q), the interval [X_(lower), X_(upper)] covers the true
    quantile with probability at least ``confidence`` for ANY distribution of
    i.i.d. samples (ties make it conservative, not invalid). ``None`` means the
    sample is too small to bound that side at all: for example no finite upper
    bound on the 99.9th percentile exists from 100 samples.
    """
    if type(n) is not int or n < 1 or isinstance(q, bool) or not isinstance(q, float) or not 0 < q < 1:
        raise ValueError("require integer n >= 1 and float 0 < q < 1")
    tail = (1 - check_confidence(confidence)) / 2
    start, mass = _binomial_window(n, q)
    lower: int | None = None
    total = 0.0
    for offset, probability in enumerate(mass):  # P(B <= k) <= tail  =>  lower = k + 1
        total += probability
        if total > tail:
            break
        lower = start + offset + 1
    upper: int | None = None
    total = 0.0
    for offset, probability in enumerate(reversed(mass)):  # P(B >= k) <= tail  =>  upper = k
        total += probability
        if total > tail:
            break
        upper = start + len(mass) - 1 - offset
    return lower, upper


def nearest_rank(n: int, q: float) -> int:
    """1-indexed nearest-rank position of the q-quantile in n sorted samples."""
    return max(1, math.ceil(q * n))


def mean_interval(values: Sequence[float], confidence: float) -> tuple[float, float, float] | None:
    """(mean, lower, upper) by the normal approximation, or None below 30 samples.

    Uses the central limit theorem with the sample standard deviation; heavy
    tails slow its convergence, so tail behaviour is reported by quantiles instead.
    """
    n = len(values)
    if n < MIN_SAMPLES_FOR_NORMAL_MEAN:
        return None
    mean = fmean(values)
    variance = math.fsum((value - mean) ** 2 for value in values) / (n - 1)
    half = NormalDist().inv_cdf(1 - (1 - check_confidence(confidence)) / 2) * math.sqrt(variance / n)
    return mean, mean - half, mean + half


def lag1_autocorrelation(values: Sequence[float]) -> float | None:
    """Sample lag-1 autocorrelation in the given order; None for a constant series."""
    mean = fmean(values)
    denominator = math.fsum((value - mean) ** 2 for value in values)
    if len(values) < 3 or denominator == 0:
        return None
    return math.fsum(
        (a - mean) * (b - mean) for a, b in pairwise(values)
    ) / denominator
