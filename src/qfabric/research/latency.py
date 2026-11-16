"""Latency distributions: tail percentiles with distribution-free uncertainty.

Input is a list of already-validated durations plus an explicit provenance
label. A point percentile without an interval says nothing about how well the
tail is resolved, so every percentile carries one, or says why none exists.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from qfabric.research import PROVENANCE
from qfabric.research.stats import (
    check_confidence,
    lag1_autocorrelation,
    mean_interval,
    nearest_rank,
    quantile_rank_interval,
    wilson_interval,
)

SCHEMA = "qfabric-latency-summary/1"
QUANTILES = (0.5, 0.9, 0.95, 0.99, 0.999)
MAX_SAMPLES = 2_000_000
MAX_THRESHOLDS = 8


def _label(value: Any, name: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 120:
        raise ValueError(f"{name} must be a bounded nonempty label")
    return value


def summarize_latency(
    values: Sequence[float], *, quantity: str, unit: str, provenance: str,
    ordered: bool, confidence: float = 0.95, thresholds: Sequence[float] = (),
) -> dict[str, Any]:
    """Summarise durations. ``ordered`` says whether the sequence is acquisition order."""
    _label(quantity, "quantity")
    _label(unit, "unit")
    if provenance not in PROVENANCE:
        raise ValueError(f"provenance must be one of {PROVENANCE}")
    if type(ordered) is not bool:
        raise TypeError("ordered must be a bool")
    check_confidence(confidence)
    n = len(values)
    if not 2 <= n <= MAX_SAMPLES:
        raise ValueError(f"require 2..{MAX_SAMPLES} latency samples")
    for value in values:
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("latency samples must be finite, non-negative numbers")
    if len(thresholds) > MAX_THRESHOLDS or any(
        type(t) not in (int, float) or not math.isfinite(t) or t < 0 for t in thresholds
    ):
        raise ValueError("thresholds must be at most 8 finite, non-negative numbers")

    ranked = sorted(values)
    quantiles = []
    for q in QUANTILES:
        lower, upper = quantile_rank_interval(n, q, confidence)
        missing = [side for side, rank in (("lower", lower), ("upper", upper)) if rank is None]
        quantiles.append({
            "probability": q,
            "estimate": ranked[nearest_rank(n, q) - 1],
            "lower": None if lower is None else ranked[lower - 1],
            "upper": None if upper is None else ranked[upper - 1],
            "lowerRank": lower,
            "upperRank": upper,
            "resolved": not missing,
            "unresolvedReason": (
                f"{n} samples cannot bound the {' and '.join(missing)} side at this confidence"
                if missing else None
            ),
        })
    mean = mean_interval(values, confidence)
    autocorrelation = lag1_autocorrelation(values) if ordered else None
    band = 3 / math.sqrt(n)
    if autocorrelation is None:
        independence = (
            "not_assessed_constant_series" if ordered else "not_assessed_sample_order_unknown"
        )
    else:
        independence = (
            "lag1_within_white_noise_band" if abs(autocorrelation) <= band
            else "lag1_outside_white_noise_band_intervals_likely_too_narrow"
        )
    exceedance = []
    for threshold in thresholds:
        count = sum(value > threshold for value in ranked)
        low, high = wilson_interval(count, n, confidence)
        exceedance.append({
            "threshold": threshold, "count": count, "fraction": count / n,
            "wilsonLower": low, "wilsonUpper": high,
        })
    return {
        "schemaVersion": SCHEMA,
        "quantity": quantity,
        "unit": unit,
        "provenance": provenance,
        "samples": n,
        "confidenceLevel": confidence,
        "minimum": ranked[0],
        "maximum": ranked[-1],
        "mean": None if mean is None else {
            "estimate": mean[0], "lower": mean[1], "upper": mean[2],
        },
        "quantiles": quantiles,
        "exceedance": exceedance,
        "lag1Autocorrelation": autocorrelation,
        "lag1WhiteNoiseBand": band,
        "independenceDiagnostic": independence,
        "methods": {
            "quantilePoint": "nearest rank, ceil(q*n)",
            "quantileInterval": "distribution-free order-statistic interval (binomial ranks)",
            "meanInterval": "normal approximation with sample standard deviation, n >= 30",
            "exceedanceInterval": "Wilson score interval",
        },
        "assumptions": [
            ("Samples are independent and identically distributed; drift or serial "
             "correlation makes every interval too narrow."),
            "Each interval has the stated confidence on its own; they are not simultaneous.",
            "The sample maximum is an observation, not a bound on the worst case.",
        ],
    }
