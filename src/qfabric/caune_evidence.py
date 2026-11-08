"""Strict offline inspection of user-supplied Caune et al. (2024) QEC figure data.

No network access, author code execution, qubit control, inferred per-shot samples,
or claim that QFabric independently measured the Rigetti/Riverlane experiment.
The metadata hashes identify *these uploaded copies*; upstream checksum and
third-party redistribution rights still require independent confirmation.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
from collections import defaultdict
from statistics import fmean
from typing import Any

PAPER_URL = "https://arxiv.org/abs/2410.05202"
DATASET_RECORD_CANDIDATE = "https://zenodo.org/records/15364358"
SCHEMA = "qfabric-caune-2024-user-supplied-data-audit/1"
CLOCK_MHZ = 156.25  # Author paper §III; 1 clock cycle = 0.0064 µs.
EXPECTED_COUNTS = {9: 100_000, 17: 100_000, 25: 100_000}
EXPECTED_SHA256 = {
    "decoder_timings_each_repetition.csv":
        "8f23b21a27004381734fefeef80e5326e0a67c391212fcb792950cf9b51bd324",
    "defect_rates_per_round.txt":
        "c923029ef8ececd2253f5efc1fe0054f549db79bdafee0671a61af1ed474ca54",
    "defect_rates_per_round_stability_9.txt":
        "ebe0126c80fbba48b3b7dc04b3b02c6857a4aef1963089ca3dd1593e3eb46f79",
}
MAX_TIMING_BYTES = 16 * 1024 * 1024
MAX_DEFECT_BYTES = 16 * 1024
MAX_TIMING_RECORDS = 400_000


def _source_check(raw: bytes, filename: str, max_bytes: int, *, enforce_pin: bool) -> str:
    if type(raw) is not bytes or not 0 < len(raw) <= max_bytes:
        raise ValueError("invalid bounded source bytes")
    digest = hashlib.sha256(raw).hexdigest()
    if enforce_pin and digest != EXPECTED_SHA256[filename]:
        raise ValueError("source SHA-256 mismatches uploaded research artifact")
    return digest


def _finite(value: str, *, lower: float = 0, upper: float = 1) -> float:
    try:
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid numeric observation") from exc
    if not math.isfinite(number) or not lower <= number <= upper:
        raise ValueError("out-of-domain or nonfinite observation")
    return number


def _rounds(value: str) -> int:
    if not value.isascii() or not value.isdecimal():
        raise ValueError("invalid integral round count")
    return int(value)


def _nearest_rank(values: list[float], probability: float) -> float:
    return values[math.ceil(probability * len(values)) - 1]


def audit_decoder_timings(
    raw: bytes, *, enforce_pin: bool = True, enforce_complete: bool = True,
) -> dict[str, Any]:
    """Audit measured-like author CSV without treating its rows as QFabric output.

    Column time_per_round is in µs, inferred from original paper's 156.25 MHz
    clock and verified against every supplied 'cycles' record. The file does
    not contain decoded outcomes, timestamps, or qubit-level syndrome records.
    """
    digest = _source_check(
        raw, "decoder_timings_each_repetition.csv", MAX_TIMING_BYTES,
        enforce_pin=enforce_pin,
    )
    text = raw.decode("utf-8", errors="strict")
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    if reader.fieldnames != ["rounds", "cycles", "time_per_round"]:
        raise ValueError("unexpected Caune decoder timing CSV schema")
    series: dict[int, list[float]] = defaultdict(list)
    n = 0
    for row in reader:
        if None in row or set(row) != set(reader.fieldnames):
            raise ValueError("unexpected extra or missing columns")
        rounds = _rounds((row["rounds"] or "").strip())
        if rounds not in EXPECTED_COUNTS:
            raise ValueError("unexpected decoding-round group")
        cycles = _finite((row["cycles"] or "").strip(), lower=1, upper=1e9)
        if not cycles.is_integer():
            raise ValueError("FPGA cycles must be integral")
        time_us = _finite((row["time_per_round"] or "").strip(), lower=0, upper=1e6)
        if time_us <= 0:
            raise ValueError("decoding time must be positive")
        expected_us = cycles / CLOCK_MHZ / rounds
        if not math.isclose(time_us, expected_us, rel_tol=1e-10, abs_tol=1e-10):
            raise ValueError("time_per_round disagrees with FPGA cycle clock")
        n += 1
        if n > MAX_TIMING_RECORDS:
            raise ValueError("too many measurements")
        series[rounds].append(time_us)
    if enforce_complete and {key: len(val) for key, val in series.items()} != EXPECTED_COUNTS:
        raise ValueError("timing CSV incomplete for original uploaded groups")
    if not n:
        raise ValueError("no timing records")
    groups = []
    for rounds in sorted(series):
        ordered = sorted(series[rounds])
        groups.append({
            "rounds": rounds,
            "records": len(ordered),
            "meanUsPerRound": fmean(ordered),
            "medianUsPerRound": _nearest_rank(ordered, 0.5),
            "p95UsPerRound": _nearest_rank(ordered, 0.95),
            "p99UsPerRound": _nearest_rank(ordered, 0.99),
            "maximumUsPerRound": ordered[-1],
            "repetitionFractionAbove1UsPerRound":
                sum(v > 1.0 for v in ordered) / len(ordered),
            "repetitionCountAbove1UsPerRound": sum(v > 1.0 for v in ordered),
        })
    return {
        "filename": "decoder_timings_each_repetition.csv",
        "sha256OfProvidedBytes": digest,
        "bytes": len(raw),
        "rowCount": n,
        "clockMHzVerifiedAgainstAllRows": CLOCK_MHZ,
        "units": "microseconds per decoding round",
        "groups": groups,
        "caveat": (
            "A repetition average above 1 µs is NOT a measured backlog probability; "
            "this file has no per-round streaming arrival/completion timestamps."
        ),
    }


def audit_defect_rates(
    raw: bytes, *, filename: str, enforce_pin: bool = True,
    enforce_complete: bool = True,
) -> dict[str, Any]:
    """Audit per-round published defect-rate estimates, not raw Bernoulli shots."""
    if filename not in {
        "defect_rates_per_round.txt", "defect_rates_per_round_stability_9.txt",
    }:
        raise ValueError("unexpected defect series")
    digest = _source_check(raw, filename, MAX_DEFECT_BYTES, enforce_pin=enforce_pin)
    text = raw.decode("utf-8", errors="strict")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2 or len(lines) > 40:
        raise ValueError("invalid defect table length")
    is_25 = filename == "defect_rates_per_round.txt"
    if is_25:
        if lines[0].split() != [
            "round", "Qubit", "50", "Qubit", "52",
            "Qubit", "36", "Qubit", "38",
        ]:
            raise ValueError("unexpected named qubit columns")
        labels = ["Qubit 50", "Qubit 52", "Qubit 36", "Qubit 38"]
    else:
        if lines[0].split() != ["round", "rate_1", "rate_2", "rate_3", "rate_4"]:
            raise ValueError("unexpected anonymous rate columns")
        labels = ["rate_1", "rate_2", "rate_3", "rate_4"]
    expected_rounds = 25 if is_25 else 27
    if enforce_complete and len(lines) != expected_rounds + 1:
        raise ValueError("unexpected source table round count")
    columns: dict[str, list[float]] = {name: [] for name in labels}
    for index, line in enumerate(lines[1:], start=1):
        cells = line.split()
        if len(cells) != 5 or _rounds(cells[0]) != index:
            raise ValueError("nonsequential round or wrong number of columns")
        for label, rate in zip(labels, cells[1:], strict=True):
            columns[label].append(_finite(rate))
    series = [{
        "label": label,
        "firstRate": values[0],
        "lastRate": values[-1],
        "differenceLastMinusFirst": values[-1] - values[0],
        "minimumRate": min(values),
        "maximumRate": max(values),
    } for label, values in columns.items()]
    return {
        "filename": filename,
        "sha256OfProvidedBytes": digest,
        "bytes": len(raw),
        "rounds": len(lines) - 1,
        "metric": "defect-rate fraction (published aggregate, shots per point unknown)",
        "series": series,
        "figureAssociation": "figure_3b_stability_8" if is_25 else "UNRESOLVED",
        "caveat": (
            "The 27-round 'stability_9' file has anonymous rate_1..4 columns; "
            "do not equate it to the nine-round decoder timing group."
            if not is_25 else
            "Per-point shot counts and covariance unavailable; no independent "
            "uncertainty interval or significance claim can be calculated."
        ),
    }


def audit_uploaded_caune_bundle(
    timings: bytes, defects25: bytes, defects_stability9: bytes, *,
    enforce_pin: bool = True, enforce_complete: bool = True,
) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA,
        "paper": PAPER_URL,
        "candidateDatasetRecordNotAuthenticated": DATASET_RECORD_CANDIDATE,
        "sourceStatus": "user_supplied_original_format_unverified_upstream_checksum",
        "provenance": "authors_reported_hardware_experiment_data_reanalysed_offline",
        "timing": audit_decoder_timings(
            timings, enforce_pin=enforce_pin, enforce_complete=enforce_complete,
        ),
        "defects25": audit_defect_rates(
            defects25, filename="defect_rates_per_round.txt",
            enforce_pin=enforce_pin, enforce_complete=enforce_complete,
        ),
        "defectsUnresolved": audit_defect_rates(
            defects_stability9, filename="defect_rates_per_round_stability_9.txt",
            enforce_pin=enforce_pin, enforce_complete=enforce_complete,
        ),
        "qfabricMeasurementsPerformed": False,
        "originalHardwareAccess": False,
        "fpgaDecoderReimplemented": False,
        "backlogObservedFromRawTimestamps": False,
        "upstreamDistributionAuthenticated": False,
        "redistributionLicenseVerified": False,
        "notes": [
            "Hashes match user-provided copies when enforce_pin=True; not independent Zenodo checksums.",
            "Mean execution time per round does not bound individual execution tails.",
            "The 9/17/25 timing groups are not the same thing as the 27-row stability_9 table.",
            "No independent logical-error probabilities or decoder-vs-decoder performance inferred.",
        ],
    }
