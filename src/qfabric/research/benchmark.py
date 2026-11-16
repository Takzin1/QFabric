"""Offline decoder benchmark: a hashed spec in, a deterministic report out.

Every decoder is checked three independent ways: against an exhaustive oracle
for every syndrome, against a closed-form count of failing errors, and by seeded
Monte Carlo whose interval must be consistent with the exact value. This tests
SOFTWARE CORRECTNESS on synthetic syndromes. It makes no statement about any
quantum device, hardware decoder, or published experimental result.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import random
import re
import time
import tracemalloc
from typing import Any

from qfabric.dataset_baseline import _exact_fields, _integer, _read_json
from qfabric.research.decoders import (
    DECODERS,
    DecodingProblem,
    coset_table,
    failing_weight_counts,
    failure_probability,
    hamming_7_4,
    judge_correction,
    repetition_code,
)
from qfabric.research.stats import check_confidence, wilson_interval

SPEC_SCHEMA = "qfabric-decoder-benchmark-spec/1"
REPORT_SCHEMA = "qfabric-decoder-benchmark-report/1"
RUNTIME_SCHEMA = "qfabric-decoder-runtime-measurement/1"
MAX_SPEC_BYTES = 16 * 1024
MAX_SHOTS = 200_000
MAX_TOTAL_SHOTS = 5_000_000
REFUSAL_NOT_SYNTHETIC = (
    "only kind 'synthetic_fixture' is accepted: no authenticated syndrome-level "
    "measurement source is registered, and aggregate timing data is not syndrome data"
)


def canonical_sha256(document: Any) -> str:
    """SHA-256 of the canonical JSON form (sorted keys, no whitespace, finite numbers)."""
    text = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _closed_form_counts(decoder: str, bits: int) -> tuple[int, ...]:
    """Textbook count of failing weight-w errors, derived without enumeration."""
    if decoder == "majority_vote":  # fails when more than half of the bits flipped
        return tuple(math.comb(bits, w) if 2 * w > bits else 0 for w in range(bits + 1))
    if decoder == "negative_control_prefix":  # fails exactly when bit 0 flipped
        return tuple(math.comb(bits - 1, w - 1) if w else 0 for w in range(bits + 1))
    return tuple(math.comb(7, w) if w >= 2 else 0 for w in range(8))  # Hamming corrects one


def _not_better(candidate: float, reference: float) -> bool:
    """True when ``candidate`` fails at least as often; equal up to float rounding counts."""
    return candidate > reference or math.isclose(candidate, reference, rel_tol=1e-9)


def _unencoded(family: str, p: float) -> float:
    """Failure probability of the same information sent with no code at all."""
    return p if family == "repetition" else 1 - (1 - p) ** 4


def parse_spec(raw: bytes) -> dict[str, Any]:
    """Validate an untrusted benchmark spec; anything unexpected is refused."""
    spec = _read_json(raw, limit=MAX_SPEC_BYTES)
    _exact_fields(spec, frozenset({
        "schemaVersion", "kind", "benchmarkId", "code", "noise", "decoders", "sampling",
    }), "benchmark spec")
    if spec["schemaVersion"] != SPEC_SCHEMA:
        raise ValueError("unsupported decoder benchmark spec schema")
    if spec["kind"] != "synthetic_fixture":
        raise ValueError(REFUSAL_NOT_SYNTHETIC)
    if not isinstance(spec["benchmarkId"], str) or not re.fullmatch(
        r"DBL-[0-9]{3}", spec["benchmarkId"]
    ):
        raise ValueError("benchmarkId must have the form DBL-000")
    code = _exact_fields(spec["code"], frozenset({"family", "sizes"}), "code")
    sizes = code["sizes"]
    if not isinstance(sizes, list) or not 1 <= len(sizes) <= 5 or len(set(sizes)) != len(sizes):
        raise ValueError("code.sizes must list 1..5 distinct block lengths")
    if code["family"] == "repetition":
        for size in sizes:
            repetition_code(size)  # raises unless odd and within 3..11
    elif code["family"] != "hamming_7_4" or sizes != [7]:
        raise ValueError("code.family must be 'repetition' or 'hamming_7_4' with sizes [7]")
    noise = _exact_fields(spec["noise"], frozenset({"model", "probabilities"}), "noise")
    probabilities = noise["probabilities"]
    if noise["model"] != "iid_bit_flip":
        raise ValueError("only the iid_bit_flip noise model is implemented")
    if (
        not isinstance(probabilities, list) or not 1 <= len(probabilities) <= 12
        or any(type(p) is not float or not 0 < p < 1 for p in probabilities)
        or sorted(set(probabilities)) != probabilities
    ):
        raise ValueError("noise.probabilities must be 1..12 increasing floats within (0, 1)")
    decoders = spec["decoders"]
    if (
        not isinstance(decoders, list) or not 1 <= len(decoders) <= 4
        or any(not isinstance(name, str) for name in decoders)
        or len(set(decoders)) != len(decoders)
    ):
        raise ValueError("decoders must list 1..4 distinct registered names")
    for name in decoders:
        if name not in DECODERS or DECODERS[name][0] != code["family"]:
            raise ValueError(f"decoder {name!r} is not registered for code family {code['family']!r}")
    sampling = _exact_fields(
        spec["sampling"], frozenset({"shots", "seed", "confidenceLevel"}), "sampling",
    )
    shots = _integer(sampling["shots"], "sampling.shots", 100, MAX_SHOTS)
    _integer(sampling["seed"], "sampling.seed", 0, 2 ** 63 - 1)
    check_confidence(sampling["confidenceLevel"])
    if shots * len(sizes) * len(probabilities) * len(decoders) > MAX_TOTAL_SHOTS:
        raise ValueError("benchmark exceeds the total sampling budget")
    return spec


def _problem(family: str, size: int) -> DecodingProblem:
    return repetition_code(size) if family == "repetition" else hamming_7_4()


def _cell_seed(seed: int, problem: str, p: float) -> int:
    """Per (code, p) seed. Decoders share it, so they see identical error samples."""
    digest = hashlib.sha256(f"{seed}|{problem}|{p!r}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _sample_failures(problem: DecodingProblem, decoder: Any, p: float, shots: int, seed: int) -> int:
    rng = random.Random(seed)
    outcome: dict[tuple[int, ...], bool] = {}
    failures = 0
    for _ in range(shots):
        error = tuple(int(rng.random() < p) for _ in range(problem.bits))
        failed = outcome.get(error)
        if failed is None:
            correction = decoder(problem, problem.syndrome(error))
            residual = tuple(a ^ b for a, b in zip(error, correction, strict=True))
            failed = outcome[error] = any(problem.logical_class(residual))
        failures += failed
    return failures


def run_decoder_benchmark(raw: bytes) -> dict[str, Any]:
    """Run the benchmark described by ``raw``. Same bytes always give the same report."""
    spec = parse_spec(raw)
    family, sizes = spec["code"]["family"], spec["code"]["sizes"]
    probabilities = spec["noise"]["probabilities"]
    shots, seed = spec["sampling"]["shots"], spec["sampling"]["seed"]
    confidence = spec["sampling"]["confidenceLevel"]

    results = []
    summary = []
    for name in spec["decoders"]:
        decoder = DECODERS[name][1]
        exact: dict[tuple[int, float], float] = {}
        agreement: list[float] = []
        covered = cells = 0
        for size in sizes:
            problem = _problem(family, size)
            verdicts = [
                judge_correction(problem, syndrome, decoder(problem, syndrome))
                for syndrome in coset_table(problem)
            ]
            counts = {key: verdicts.count(key) for key in ("agree", "disagree", "ambiguous", "invalid")}
            decided = len(verdicts) - counts["ambiguous"]
            agreement.append(counts["agree"] / decided if decided else 0.0)
            failing = failing_weight_counts(problem, decoder)
            closed = _closed_form_counts(name, problem.bits)
            points = []
            for p in probabilities:
                cell_seed = _cell_seed(seed, problem.name, p)
                failures = _sample_failures(problem, decoder, p, shots, cell_seed)
                low, high = wilson_interval(failures, shots, confidence)
                exact[size, p] = truth = failure_probability(failing, p)
                cells += 1
                covered += low <= truth <= high
                points.append({
                    "probability": p,
                    "cellSeed": cell_seed,
                    "shots": shots,
                    "failures": failures,
                    "failureRate": failures / shots,
                    "wilsonLower": low,
                    "wilsonUpper": high,
                    "exactFailureProbability": truth,
                    "closedFormFailureProbability": failure_probability(closed, p),
                    "intervalCoversExact": low <= truth <= high,
                    "unencodedFailureProbability": _unencoded(family, p),
                    "resolution": (
                        "upper_bound_only_zero_failures" if failures == 0
                        else "lower_bound_only_all_failures" if failures == shots
                        else "resolved"
                    ),
                })
            results.append({
                "code": problem.name, "bits": problem.bits, "checks": len(problem.checks),
                "decoder": name, "syndromes": len(verdicts), "oracle": counts,
                "failingErrorsByWeight": list(failing),
                "closedFormFailingErrorsByWeight": list(closed),
                "closedFormMatchesEnumeration": failing == closed,
                "points": points,
            })
        summary.append({
            "decoder": name,
            "oracleAgreementFraction": min(agreement),
            "intervalCoverageFraction": covered / cells,
            "intervalMisses": cells - covered,
            "intervalMissesExpectedAtNominalCoverage": cells * (1 - confidence),
            "failureRegions": {
                # Where the code stops paying for itself, read from exact values.
                "noBenefitOverUnencoded": [
                    {"bits": size, "probability": p}
                    for size in sizes for p in probabilities
                    if _not_better(exact[size, p], _unencoded(family, p))
                ],
                "noBenefitFromLargestCode": [
                    p for p in probabilities
                    if len(sizes) > 1 and _not_better(exact[max(sizes), p], exact[min(sizes), p])
                ],
            },
        })
    report = {
        "schemaVersion": REPORT_SCHEMA,
        "kind": "synthetic_decoder_benchmark",
        "benchmarkId": spec["benchmarkId"],
        "specSha256": hashlib.sha256(raw).hexdigest(),
        "comparisonTests": "software_correctness",
        "dataProvenance": "synthetic",
        "syndromeSource": "seeded pseudo-random i.i.d. bit flips (Python random.Random)",
        "seed": seed,
        "confidenceLevel": confidence,
        "summary": summary,
        "results": results,
        "statisticalAssumptions": [
            "Shots are independent Bernoulli trials by construction of the sampler.",
            "Wilson intervals have nominal, not guaranteed, coverage; each is marginal.",
            "Decoders share error samples within a (code, probability) cell.",
        ],
        "limitations": [
            "Classical codes of at most 12 bits under bit-flip noise; not a surface code.",
            "No measured syndromes, circuit-level noise, leakage or correlated errors.",
            "Agreement with an exhaustive oracle is not evidence about any hardware decoder.",
        ],
        "measuredSyndromeDataUsed": False,
        "hardwareExecuted": False,
        "publishedResultReproduced": False,
    }
    return {**report, "resultDigest": canonical_sha256(report)}


def measure_runtime(raw: bytes, *, repeats: int = 5) -> dict[str, Any]:
    """Time each decoder on this host. Real measurements, so NOT reproducible bit-for-bit.

    Procedure: decode every syndrome of the code once per pass; report the
    fastest of ``repeats`` passes (least disturbed by other load) and the peak
    traced allocation of one separate pass.
    """
    spec = parse_spec(raw)
    _integer(repeats, "repeats", 1, 50)
    rows = []
    for name in spec["decoders"]:
        decoder = DECODERS[name][1]
        for size in spec["code"]["sizes"]:
            problem = _problem(spec["code"]["family"], size)
            syndromes = list(coset_table(problem))
            passes = []
            for _ in range(repeats):
                started = time.perf_counter_ns()
                for syndrome in syndromes:
                    decoder(problem, syndrome)
                passes.append(time.perf_counter_ns() - started)
            tracemalloc.start()
            for syndrome in syndromes:
                decoder(problem, syndrome)
            peak = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            rows.append({
                "code": problem.name, "decoder": name, "syndromesPerPass": len(syndromes),
                "bestPassNanosecondsPerDecode": min(passes) / len(syndromes),
                "worstPassNanosecondsPerDecode": max(passes) / len(syndromes),
                "peakTracedBytes": peak,
            })
    return {
        "schemaVersion": RUNTIME_SCHEMA,
        "kind": "host_software_timing",
        "specSha256": hashlib.sha256(raw).hexdigest(),
        "provenance": "measured",
        "measuredObject": "these pure-Python reference decoders on the reporting host",
        "procedure": (
            f"time.perf_counter_ns around one pass over every syndrome, {repeats} passes; "
            "tracemalloc peak for one further pass"
        ),
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "system": platform.system(),
            "machine": platform.machine(),
        },
        "rows": rows,
        "reproducibleBitForBit": False,
        "comparableToHardwareDecoderLatency": False,
        "gpuUsed": False,
    }
