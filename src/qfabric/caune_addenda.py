"""Bounded audit of two additional user-supplied Caune figure summaries.

The 9/17/25 mean times are already independently recomputed in
caune_evidence.audit_decoder_timings from 300,000 author observations.
Do not import them as three new experimental observations.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any

SCHEMA = "qfabric-caune-summary-addenda/1"
PAPER = "https://arxiv.org/abs/2410.05202"
MEAN_NAME = "mean_decoding_time.txt"
STABILITY_NAME = "lep_mwpm_stability_9.txt"
SHA256 = {
    MEAN_NAME: "0e163c3b8c7c80140333f4a1832396248466c10d150fa08da39a6d58b5d1bf30",
    STABILITY_NAME: "d5d8b1d9ee0937e8b154ee40a681705d127fd7ad709df8784f0813a1b453e001",
}
MEAN_ROUNDS = tuple(range(3, 26, 2))
STABILITY_ROUNDS = tuple(range(5, 28, 2))
# Rounded from the earlier 300k original-record audit; tolerance is
# half the last displayed 6-decimal place plus float representation margin.
ALREADY_RECOMPUTED = {9: 0.483114, 17: 0.646869, 25: 0.796577}


def _read_table(
    raw: bytes, filename: str, header: list[str], rounds: tuple[int, ...],
    *, enforce_pin: bool, enforce_complete: bool,
) -> tuple[list[dict[str, float | int]], str]:
    if filename not in SHA256 or type(raw) is not bytes or not 0 < len(raw) <= 4096:
        raise ValueError("unknown, empty or oversized summary file")
    digest = hashlib.sha256(raw).hexdigest()
    if enforce_pin and digest != SHA256[filename]:
        raise ValueError("source SHA-256 does not match uploaded bytes")
    lines = [line.split() for line in raw.decode("utf-8", errors="strict").splitlines()
             if line.strip()]
    if not lines or lines[0] != header or len(lines) < 2 or len(lines) > 50:
        raise ValueError("wrong author table header or row count")
    results = []
    for values in lines[1:]:
        if len(values) != 3 or not values[0].isascii() or not values[0].isdecimal():
            raise ValueError("expected indexed value/error row")
        n = int(values[0])
        if n not in rounds or (results and n <= results[-1]["rounds"]):
            raise ValueError("unexpected, duplicate or unordered round")
        try:
            value, err = float(values[1]), float(values[2])
        except ValueError as exc:
            raise ValueError("non-numeric author point") from exc
        upper = 1 if filename == STABILITY_NAME else 10
        if (not math.isfinite(value) or not math.isfinite(err) or
                not 0 <= value <= upper or not 0 < err <= upper):
            raise ValueError("value/error not finite or out of domain")
        results.append({"rounds": n, "value": value, "reportedError": err})
    if enforce_complete and tuple(p["rounds"] for p in results) != rounds:
        raise ValueError("incomplete original summary series")
    return results, digest


def audit_additional_summaries(
    mean_raw: bytes, stability_raw: bytes, *,
    enforce_pin: bool = True, enforce_complete: bool = True,
) -> dict[str, Any]:
    times, mean_sha = _read_table(
        mean_raw, MEAN_NAME, ["time", "(us)", "err"], MEAN_ROUNDS,
        enforce_pin=enforce_pin, enforce_complete=enforce_complete,
    )
    stability, lep_sha = _read_table(
        stability_raw, STABILITY_NAME, ["lep", "std"], STABILITY_ROUNDS,
        enforce_pin=enforce_pin, enforce_complete=enforce_complete,
    )
    existing = []
    new = []
    for row in times:
        rounds = row["rounds"]
        value = row["value"]
        if rounds in ALREADY_RECOMPUTED:
            baseline = ALREADY_RECOMPUTED[rounds]
            if abs(value - baseline) > 0.00000051:
                raise ValueError("author summary differs from 300k raw timing recomputation")
            existing.append({
                **row, "alreadyRecomputedMeanUs": baseline,
                "classification": "existing_mean_crosscheck_not_new_data",
            })
        else:
            new.append({
                **row, "classification": "additional_round_mean_and_reported_error",
            })
    return {
        "schemaVersion": SCHEMA, "paper": PAPER,
        "sourceStatus": "user_supplied_copies_not_authoritative_zenodo_checksum",
        "sourceSha256": {MEAN_NAME: mean_sha, STABILITY_NAME: lep_sha},
        "meanDecodingTime": {
            "metric": "mean decoding time in microseconds per round",
            "sourceRoundCount": len(times),
            "alreadyRecomputedOverlap": existing,
            "additionalRoundSummaries": new,
            "authorReportedErrorMeaning": "unverified_from_table_alone",
            "doNotCountOverlapAsIndependentExperiments": True,
        },
        "stability9Mwpm": {
            "sourceRoundCount": len(stability),
            "observations": stability,
            "metric": "author-reported logical error probability (fraction)",
            "experiment": "stability_9_per_filename_not_stability_8",
            "authorReportedStdMeaning": "not_verified_from_table_alone",
            "paperFigureAssociation": "UNRESOLVED",
            "directComparisonToStability8Permitted": False,
        },
        "independentHardwareMeasurementPerformed": False,
        "originalRawShotRecordsForStability9Provided": False,
        "sourceRedistributionRightsVerified": False,
    }
