"""Offline paper-to-source audit for Caune et al. 2024, Fig. 4 and SI Fig. 4.

All inputs are user-provided copies of author-published derived figure data.
Neither QFabric nor this module acquired quantum hardware measurements.
No third-party raw files are checked in. SHA pins authenticate only the
supplied copy, not the authoritative Zenodo provenance or redistribution rights.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
import re
from collections import defaultdict
from typing import Any

PAPER_URL = "https://arxiv.org/abs/2410.05202"
SCHEMA = "qfabric-caune-feedback-figure-audit/1"
PAPER_T1_US = 13.0  # Author's E1 reference (13 +/- 1 µs), not a QFabric calibration.
SOURCE_SHA256 = {
    "fig4b_decoding_response_time.csv":
        "00155d0e94fb799679476ca759d71edd2c3a21cc6967a80d20244e3c150ea2a4",
    "figS4c_feedback_response_time_probability_density_data.csv":
        "48e5e19a74316d34d3a4819d5e88707e90a0a863e16e74e6f8bf682eec4fc61a",
    "figS4c_feedback_response_time_probability_density_fit_parameters.csv":
        "f56ae6a00dc8adbcfd344fed8a1f5a6105df1eb91bdc2202330eb80ed4ac295f",
    "figS4d_t1_time_fitting.csv":
        "94c135e6e6d5eb40cc078becc7bfe866aa2e2a72cda7bad53162891df16d117e",
}
MAX_CSV_BYTES = 32 * 1024
ROUNDS = tuple(range(2, 10))


def _source(raw: bytes, filename: str, *, enforce_pin: bool) -> tuple[str, str]:
    if filename not in SOURCE_SHA256 or type(raw) is not bytes or not 0 < len(raw) <= MAX_CSV_BYTES:
        raise ValueError("unknown, empty or oversized Caune figure source")
    digest = hashlib.sha256(raw).hexdigest()
    if enforce_pin and digest != SOURCE_SHA256[filename]:
        raise ValueError("source SHA-256 differs from user-supplied copy")
    return raw.decode("utf-8", errors="strict"), digest


def _csv(raw: bytes, filename: str, columns: list[str], *, enforce_pin: bool) -> tuple[list[dict[str, str]], str]:
    text, digest = _source(raw, filename, enforce_pin=enforce_pin)
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    if reader.fieldnames != columns:
        raise ValueError(f"unexpected schema for {filename}")
    rows = []
    for row in reader:
        if None in row or set(row) != set(columns) or any(v is None or not v.strip() for v in row.values()):
            raise ValueError(f"invalid columns for {filename}")
        rows.append(row)
        if len(rows) > 500:
            raise ValueError("too many rows")
    if not rows:
        raise ValueError("empty CSV")
    return rows, digest


def _float(raw: str, *, positive: bool = False, ceiling: float = 1e9) -> float:
    try:
        number = float(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid numeric value") from exc
    if not math.isfinite(number) or number < 0 or number > ceiling or (positive and number <= 0):
        raise ValueError("nonfinite or out-of-range numeric value")
    return number


def _int(raw: str) -> int:
    if not raw.isascii() or not raw.isdecimal():
        raise ValueError("invalid integer")
    return int(raw)


def _round_sequence(records: list[dict[str, str]], *, enforce_complete: bool) -> list[int]:
    rounds = [_int(r["rounds"]) for r in records]
    if len(set(rounds)) != len(rounds) or any(n not in ROUNDS for n in rounds):
        raise ValueError("duplicate or unexpected rounds")
    if rounds != sorted(rounds):
        raise ValueError("rounds out of order")
    if enforce_complete and rounds != list(ROUNDS):
        raise ValueError("incomplete 2..9 series")
    return rounds


def audit_fig4b(raw: bytes, *, enforce_pin: bool = True, enforce_complete: bool = True) -> dict[str, Any]:
    """Convert FPGA-domain ns to µs; retain qubit-derived delay in source µs."""
    name = "fig4b_decoding_response_time.csv"
    columns = [
        "rounds", "control_system_logic", "control_system_logic_std",
        "decoding_time", "decoding_time_std",
        "delay_measured_by_qubit", "delay_measured_by_qubit_std",
    ]
    records, digest = _csv(raw, name, columns, enforce_pin=enforce_pin)
    _round_sequence(records, enforce_complete=enforce_complete)
    entries = []
    for row in records:
        total_ns = _float(row["control_system_logic"], positive=True)
        total_sd_ns = _float(row["control_system_logic_std"])
        decoder_ns = _float(row["decoding_time"], positive=True)
        decoder_sd_ns = _float(row["decoding_time_std"])
        qubit_us = _float(row["delay_measured_by_qubit"], positive=True)
        qubit_sd_us = _float(row["delay_measured_by_qubit_std"])
        if decoder_ns > total_ns:
            raise ValueError("decoder duration cannot exceed total control response")
        entries.append({
            "rounds": _int(row["rounds"]),
            "controlSystemTotalUsInterpretedFromPaper": total_ns / 1000,
            "controlSystemTotalStdUs": total_sd_ns / 1000,
            "fpgaDecoderUs": decoder_ns / 1000,
            "fpgaDecoderStdUs": decoder_sd_ns / 1000,
            "differenceNonDecoderUs": (total_ns - decoder_ns) / 1000,
            "qubitInferredDelayUs": qubit_us,
            "qubitInferredStdUs": qubit_sd_us,
            "qubitMinusControlUs": qubit_us - total_ns / 1000,
        })
    return {
        "filename": name, "sha256OfProvidedBytes": digest, "rows": len(records),
        "figure": "main_Figure_4b",
        "originalFpgaFieldsUnitInterpreted": "nanoseconds (paper approx. 9.6 µs at round 9)",
        "originalQubitFieldsUnitInterpreted": "microseconds",
        "entries": entries,
        "scope": "author figure-level summary; not raw per-shot FPGA or qubit timestamps",
    }


def audit_si_density(raw: bytes, *, enforce_pin: bool = True, enforce_complete: bool = True) -> dict[str, Any]:
    name = "figS4c_feedback_response_time_probability_density_data.csv"
    rows, digest = _csv(raw, name, ["rounds", "times", "gaussian_kde_probability"], enforce_pin=enforce_pin)
    groups: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for row in rows:
        n = _int(row["rounds"])
        if n not in ROUNDS:
            raise ValueError("unexpected density series")
        x = _float(row["times"], positive=True)
        y = _float(row["gaussian_kde_probability"])
        if groups[n] and x <= groups[n][-1][0]:
            raise ValueError("density sampling times must be strictly increasing")
        groups[n].append((x, y))
    if enforce_complete and {n: len(v) for n, v in groups.items()} != {
        2: 30, **{n: 50 for n in range(3, 10)}
    }:
        raise ValueError("incomplete original KDE sampling grid")
    series = []
    for rounds in sorted(groups):
        samples = groups[rounds]
        if len(samples) < 2:
            raise ValueError("KDE series needs two or more grid points")
        area = sum(
            (samples[i][1] + samples[i + 1][1]) * (samples[i + 1][0] - samples[i][0]) / 2
            for i in range(len(samples) - 1)
        )
        series.append({
            "rounds": rounds, "samples": len(samples),
            "firstTimeUs": samples[0][0], "lastTimeUs": samples[-1][0],
            "sampleWindowTrapezoidArea": area,
            "maximumKdeDensityPerUs": max(v for _, v in samples),
        })
    return {
        "filename": name, "sha256OfProvidedBytes": digest, "rows": len(rows),
        "figure": "supplementary_Figure_4c",
        "dataKind": "authors_Gaussian_KDE_values_on_truncated_grid_not_raw_shots",
        "series": series,
        "densityWindowNotRequiredToIntegrateToOne": True,
    }


def audit_si_gamma(raw: bytes, *, t1_us: float = PAPER_T1_US,
                   enforce_pin: bool = True, enforce_complete: bool = True) -> dict[str, Any]:
    name = "figS4c_feedback_response_time_probability_density_fit_parameters.csv"
    rows, digest = _csv(raw, name, ["rounds", "k", "theta"], enforce_pin=enforce_pin)
    _round_sequence(rows, enforce_complete=enforce_complete)
    _float(str(t1_us), positive=True)
    entries = []
    for row in rows:
        k = _float(row["k"], positive=True)
        theta = _float(row["theta"], positive=True)
        mean = k * theta
        # Original Supplementary Appendix E Eq. (E13); log1p preserves accuracy.
        t1_effective = t1_us * k * math.log1p(theta / t1_us)
        if not math.isfinite(mean) or not math.isfinite(t1_effective):
            raise ValueError("invalid Gamma moment")
        entries.append({
            "rounds": _int(row["rounds"]), "gammaShapeK": k,
            "gammaScaleThetaUs": theta, "gammaMeanUs": mean,
            "gammaStdUs": math.sqrt(k) * theta,
            "t1EffectiveUsByAppendixE13": t1_effective,
            "t1EstimatorBiasMeanMinusEffectiveUs": mean - t1_effective,
            "t1EstimatorRelativeBias": (mean - t1_effective) / mean,
        })
    return {
        "filename": name, "sha256OfProvidedBytes": digest, "rows": len(rows),
        "figure": "supplementary_Figure_4c",
        "t1ForE13Us": t1_us, "t1Source": "paper_Equation_E1" if t1_us == PAPER_T1_US else "caller_supplied",
        "entries": entries,
        "model": "authors_gamma_fit_parameters_only_no_raw_timing_fit_reproduced",
    }


_VALUE_UNCERTAINTY = re.compile(r"^(0(?:\.\d+)?|1(?:\.0+)?)(?:\+/-)(0(?:\.\d+)?|1(?:\.0+)?)$")


def _weighted_exponential_fit(points: list[tuple[float, float, float]]) -> dict[str, float]:
    """Profile out A,B via weighted least squares; optimize T1 deterministically.

    m(t)=A exp(-t/T1)+B. Not a proof that qubit decay is strictly Markovian.
    """
    def loss(lifetime: float) -> tuple[float, float, float]:
        weighted = [(math.exp(-t / lifetime), y, 1 / (sigma * sigma))
                    for t, y, sigma in points]
        sw = sum(w for x, y, w in weighted)
        sx = sum(w * x for x, y, w in weighted)
        sxx = sum(w * x * x for x, y, w in weighted)
        sy = sum(w * y for x, y, w in weighted)
        sxy = sum(w * x * y for x, y, w in weighted)
        den = sw * sxx - sx * sx
        if den <= 0:
            raise ValueError("degenerate T1 reference fit")
        a = (sw * sxy - sx * sy) / den
        b = (sxx * sy - sx * sxy) / den
        chi2 = sum(w * (y - (a * x + b)) ** 2 for x, y, w in weighted)
        return chi2, a, b

    # Unique physical fit over declared positive T1 window for source-specific data.
    lo, hi = 2.0, 80.0
    factor = (math.sqrt(5) - 1) / 2
    c, d = hi - factor * (hi - lo), lo + factor * (hi - lo)
    for _ in range(110):
        if loss(c)[0] < loss(d)[0]:
            hi, d = d, c
            c = hi - factor * (hi - lo)
        else:
            lo, c = c, d
            d = lo + factor * (hi - lo)
    t1 = (lo + hi) / 2
    chi2, a, b = loss(t1)
    if not (2.001 < t1 < 79.999 and 0 <= a <= 1 and 0 <= b <= 1):
        raise ValueError("T1 fit outside bounded physical reference window")
    return {"fittedAmplitudeA": a, "fittedT1Us": t1,
            "fittedOffsetB": b, "weightedChiSquared": chi2,
            "degreesOfFreedom": len(points) - 3}


def audit_si_t1(raw: bytes, *, enforce_pin: bool = True, enforce_complete: bool = True) -> dict[str, Any]:
    name = "figS4d_t1_time_fitting.csv"
    rows, digest = _csv(raw, name, ["", "delay_time", "excited_state_population"],
                        enforce_pin=enforce_pin)
    if enforce_complete and len(rows) != 13:
        raise ValueError("incomplete original T1 reference")
    points = []
    for index, row in enumerate(rows):
        if _int(row[""]) != index:
            raise ValueError("nonsequential T1 row number")
        delay = _float(row["delay_time"])
        if points and delay <= points[-1][0]:
            raise ValueError("nonincreasing T1 delay")
        m = _VALUE_UNCERTAINTY.fullmatch(row["excited_state_population"].strip())
        if not m:
            raise ValueError("T1 population must include uncertainty with '+/-'")
        population, sigma = map(float, m.groups())
        if not 0 <= population <= 1 or not 0 < sigma < 1:
            raise ValueError("invalid T1 probability or uncertainty")
        points.append((delay, population, sigma))
    if len(points) < 4:
        raise ValueError("insufficient T1 fit data")
    return {
        "filename": name, "sha256OfProvidedBytes": digest, "rows": len(points),
        "figure": "supplementary_Figure_4d",
        "excitedStatePopulationFirst": points[0][1],
        "excitedStatePopulationLast": points[-1][1],
        "delayUnitInterpreted": "microseconds",
        "fit": _weighted_exponential_fit(points),
        "paperReportedT1Us": PAPER_T1_US,
        "paperReportedT1UncertaintyUs": 1.0,
        "scope": "weighted fit of author-provided reference averages, not raw qubit shots",
    }


def audit_caune_feedback_figures(
    fig4b: bytes, density: bytes, gamma: bytes, t1: bytes, *,
    enforce_pin: bool = True, enforce_complete: bool = True,
) -> dict[str, Any]:
    timing = audit_fig4b(fig4b, enforce_pin=enforce_pin, enforce_complete=enforce_complete)
    kde = audit_si_density(density, enforce_pin=enforce_pin, enforce_complete=enforce_complete)
    gamma_fit = audit_si_gamma(gamma, enforce_pin=enforce_pin, enforce_complete=enforce_complete)
    t1_fit = audit_si_t1(t1, enforce_pin=enforce_pin, enforce_complete=enforce_complete)
    total_by_round = {r["rounds"]: r for r in timing["entries"]}
    compare = []
    for row in gamma_fit["entries"]:
        obs = total_by_round.get(row["rounds"])
        if obs is None:
            raise ValueError("Gamma fit without matching FPGA total-time row")
        compare.append({
            "rounds": row["rounds"],
            "totalControlMeanUs": obs["controlSystemTotalUsInterpretedFromPaper"],
            "gammaFitMeanUs": row["gammaMeanUs"],
            "gammaFitMinusControlMeanUs":
                row["gammaMeanUs"] - obs["controlSystemTotalUsInterpretedFromPaper"],
        })
    if {r["rounds"] for r in kde["series"]} != set(total_by_round):
        raise ValueError("KDE and FPGA round groups disagree")
    return {
        "schemaVersion": SCHEMA,
        "paper": PAPER_URL,
        "sourceStatus": "user_supplied_copies_no_authoritative_zenodo_hash_verified",
        "fig4b": timing, "supplementaryKde": kde,
        "supplementaryGamma": gamma_fit, "supplementaryT1": t1_fit,
        "gammaVersusFpgaMean": compare,
        "physicalHardwareExecutedByQFabric": False,
        "paperFullFeedbackExperimentReproduced": False,
        "originalQuantumMeasurementsReacquired": False,
        "originalShotSamplesAvailable": False,
        "rawDataRedistributionRightsVerified": False,
        "notes": [
            "Fig4b source control_system_logic header interpreted as entire FPGA timed response based on Figure 4(b) and its ~9.6 microsecond value.",
            "Qubit-inferred delay is an independent estimate with reported standard error; do not treat as an FPGA clock timestamp.",
            "Gamma mean and Eq. E13 expectation are inferred from author-fit k/theta, not independently fitted raw Gamma samples.",
            "Gaussian KDE data have finite plotting windows; numerical integral need not be exactly one.",
            "T1 fit uses aggregate population +/- provided uncertainty, not new qubit measurements.",
        ],
    }
