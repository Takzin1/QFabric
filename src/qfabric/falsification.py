"""Paper-linked independent source leads and synthetic-only falsification checks.

No source archives, pickle files, hardware observations or model code are loaded.
A confidence interval is conditional on independent Bernoulli trial assumptions.
"""

from __future__ import annotations

import hashlib
import math
import re
from statistics import NormalDist
from typing import Any

from qfabric.dataset_baseline import (
    MAX_CATALOG_BYTES,
    MAX_COUNTS_BYTES,
    MAX_SHOTS,
    _exact_fields,
    _integer,
    _read_json,
    _text,
)

SOURCES_SCHEMA = "qfabric-independent-baseline-sources/1"
EXPERIMENT_SCHEMA = "qfabric-falsification-synthetic/1"
RESULT_SCHEMA = "qfabric-falsification-report/1"
_SOURCE_FIELDS = frozenset({
    "id", "title", "paperUrl", "datasetUrl", "datasetVersion", "filename",
    "format", "publishedMd5", "dataOrigin", "hardwareFamily", "evaluationAxis",
    "licenseClaim", "note", "downloadStatus", "localSha256",
    "licenseVerified", "measurementsVerified", "reproduced",
})
_AXES = {
    "mirror_rb_crosstalk", "mid_circuit_measurement_spectator",
    "gate_set_tomography_validation", "quantum_volume_external_validity",
}
_ORIGINS = {"mixed_claim", "simulation_claim"}
_FORMATS = {"zip": ".zip", "pcl": ".pcl", "csv": ".csv"}
_RECORDS = {
    "ALT-001": (
        "https://zenodo.org/records/5176787", "mirror_rb_crosstalk",
        "supplement.zip", "9819b53690917dfffd5aa55485a3ec92",
    ),
    "ALT-002": (
        "https://zenodo.org/records/6815663", "mid_circuit_measurement_spectator",
        "mcm-rb-IBM-code.zip", "6c5f5b505941af0dc32a1681758d5194",
    ),
    "ALT-003": (
        "https://zenodo.org/records/17523497", "gate_set_tomography_validation",
        "GST_valid_data_mixed.pcl", "4b2a8bec69e7fc5477eae760a1b3e943",
    ),
    "ALT-004": (
        ("https://darus.uni-stuttgart.de/dataset.xhtml?persistentId="
         "doi%3A10.18419%2FDARUS-5322"),
        "quantum_volume_external_validity",
        "data_fig_3acarbon1_carbon2.csv", "983a5ff5607dc31d6fa6e6d0aeacbde0",
    ),
}


def validate_baseline_sources(raw: bytes) -> dict[str, Any]:
    """Require exactly the reviewed bibliography leads; never certify raw files."""
    doc = _read_json(raw, limit=MAX_CATALOG_BYTES)
    _exact_fields(doc, frozenset({"schemaVersion", "reviewedOn", "sources"}), "sources")
    if doc["schemaVersion"] != SOURCES_SCHEMA or doc["reviewedOn"] != "2026-10-19":
        raise ValueError("unsupported independent-source schema/date")
    items = doc["sources"]
    if not isinstance(items, list) or len(items) != len(_RECORDS):
        raise ValueError("four research-source leads are required")
    ids: set[str] = set()
    for record in items:
        entry = _exact_fields(record, _SOURCE_FIELDS, "independent source")
        key = entry["id"]
        if not isinstance(key, str) or key not in _RECORDS or key in ids:
            raise ValueError("source ID must be unique and registered")
        ids.add(key)
        url, axis, filename, md5 = _RECORDS[key]
        if (
            entry["datasetUrl"] != url or entry["evaluationAxis"] != axis
            or entry["filename"] != filename or entry["publishedMd5"] != md5
        ):
            raise ValueError("source URL/axis/file/checksum differs from pinned lead")
        if entry["evaluationAxis"] not in _AXES:
            raise ValueError("unknown baseline axis")
        fmt = entry["format"]
        if not isinstance(fmt, str) or fmt not in _FORMATS:
            raise ValueError("unsupported source file type")
        if not filename.endswith(_FORMATS[fmt]):
            raise ValueError("source filename/format mismatch")
        if (
            entry["dataOrigin"] not in _ORIGINS
            or (key == "ALT-003" and entry["dataOrigin"] != "simulation_claim")
            or (key != "ALT-003" and entry["dataOrigin"] != "mixed_claim")
        ):
            raise ValueError("simulation and mixed-source claims must remain separate")
        paper = entry["paperUrl"]
        if not isinstance(paper, str) or not re.fullmatch(
            r"https://(?:doi\.org/10\.[0-9]{4,9}/[^\s?#]+|arxiv\.org/abs/[0-9]{4}\.[0-9]{4,5})",
            paper,
        ):
            raise ValueError("paper must be pinned to an original DOI/arXiv URL")
        for attr, limit in (
            ("title", 260), ("datasetVersion", 80), ("hardwareFamily", 80),
            ("licenseClaim", 180), ("note", 500),
        ):
            _text(entry[attr], attr, limit)
        if (
            entry["downloadStatus"] != "not_downloaded"
            or entry["localSha256"] is not None
            or entry["licenseVerified"] is not False
            or entry["measurementsVerified"] is not False
            or entry["reproduced"] is not False
        ):
            raise ValueError("uninspected source lead must never claim scientific verification")
    return doc


def _number(value: Any, name: str, lower: float, upper: float, *, strict: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise TypeError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(result) or not (
        lower < result < upper if strict else lower <= result <= upper
    ):
        raise ValueError(f"{name} out of supported numeric range")
    return result


def _wilson(k: int, n: int, z: float) -> tuple[float, float]:
    p = k / n
    z2 = z * z
    den = 1 + z2 / n
    center = (p + z2 / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / den
    return max(0.0, center - half), min(1.0, center + half)


def _assess_profile(profile: Any, allowed_ids: set[str]) -> dict[str, Any]:
    fields = frozenset({
        "id", "sourceBaselineId", "metric", "claim", "direction",
        "minimumImprovement", "sensitivityThresholds", "confidenceLevel",
        "minimumShotsPerArm", "samplingAssumption", "control", "candidate",
        "analysisPlan", "noiseModel",
    })
    p = _exact_fields(profile, fields, "falsification profile")
    ident = _text(p["id"], "id", 80)
    if not re.fullmatch(r"FAL-[0-9]{3}", ident):
        raise ValueError("invalid falsification profile ID")
    if p["sourceBaselineId"] not in allowed_ids:
        raise ValueError("sourceBaselineId must refer to a reviewed source lead")
    if p["metric"] != "binary_outcome_probability":
        raise ValueError("count baseline supports only a binary-outcome probability")
    _text(p["claim"], "claim", 320)
    if p["direction"] not in {"lower_is_better", "higher_is_better"}:
        raise ValueError("invalid direction")
    threshold = _number(p["minimumImprovement"], "minimumImprovement", 0.0, 1.0)
    alpha_conf = _number(p["confidenceLevel"], "confidenceLevel", 0.80, 0.999, strict=True)
    minimum_n = _integer(p["minimumShotsPerArm"], "minimumShotsPerArm", 30, 1_000_000)
    if p["samplingAssumption"] != "independent_bernoulli":
        raise ValueError("paired/clustered/drifting trials require a separate validated method")
    if p["noiseModel"] != "synthetic_independent_only":
        raise ValueError("measured and correlated noise cannot use the synthetic count baseline")
    if p["analysisPlan"] != "pre_declared_single_primary_threshold":
        raise ValueError("post-hoc threshold selection is not confirmatory")
    levels = p["sensitivityThresholds"]
    if not isinstance(levels, list) or len(levels) > 10:
        raise ValueError("sensitivity thresholds must be an array of up to 10 numbers")
    sensitivities = [_number(v, "sensitivityThreshold", 0.0, 1.0) for v in levels]
    if len(set(sensitivities)) != len(sensitivities) or threshold in sensitivities:
        raise ValueError("sensitivity thresholds must be distinct from the primary threshold")

    arms: list[tuple[int, int]] = []
    for label in ("control", "candidate"):
        arm = _exact_fields(p[label], frozenset({"shots", "events"}), label)
        n = _integer(arm["shots"], f"{label}.shots", minimum_n, MAX_SHOTS)
        k = _integer(arm["events"], f"{label}.events", 0, n)
        arms.append((k, n))
    (kc, nc), (kt, nt) = arms
    control_rate, candidate_rate = kc / nc, kt / nt
    # Union bound: each Wilson interval is nominal (1-alpha/2) coverage, so
    # simultaneous coverage of both is at least 1-alpha under binomial assumptions.
    alpha = 1 - alpha_conf
    z = NormalDist().inv_cdf(1 - alpha / 4)
    lo_control, hi_control = _wilson(kc, nc, z)
    lo_candidate, hi_candidate = _wilson(kt, nt, z)
    if p["direction"] == "lower_is_better":
        improvement = control_rate - candidate_rate
        lower, upper = lo_control - hi_candidate, hi_control - lo_candidate
    else:
        improvement = candidate_rate - control_rate
        lower, upper = lo_candidate - hi_control, hi_candidate - lo_control

    def classify(limit: float) -> str:
        if lower > limit:
            return "consistent_with_improvement"
        if upper < limit:
            return "falsifies_minimum_improvement"
        return "inconclusive"

    return {
        "id": ident,
        "sourceBaselineId": p["sourceBaselineId"],
        "claim": p["claim"],
        "primaryThreshold": threshold,
        "primaryVerdict": classify(threshold),
        "controlRate": control_rate,
        "candidateRate": candidate_rate,
        "estimatedImprovement": improvement,
        "conservativeConfidenceLevel": alpha_conf,
        "conservativeDifferenceLower": lower,
        "conservativeDifferenceUpper": upper,
        "sensitivityExploratoryOnly": [
            {"threshold": t, "verdict": classify(t)} for t in sensitivities
        ],
        "trialAssumption": p["samplingAssumption"],
        "measurementVerified": False,
        "scientificReplication": False,
        "hardwareExecuted": False,
    }


def evaluate_synthetic_falsification(raw: bytes, *, sources_raw: bytes) -> dict[str, Any]:
    """Never accept a measured input disguised as a synthetic fixture."""
    source_catalog = validate_baseline_sources(sources_raw)
    experiment = _read_json(raw, limit=MAX_COUNTS_BYTES)
    _exact_fields(experiment, frozenset({"schemaVersion", "kind", "profiles"}), "experiment")
    if (
        experiment["schemaVersion"] != EXPERIMENT_SCHEMA
        or experiment["kind"] != "synthetic_fixture"
    ):
        raise ValueError("only named synthetic fixtures may be assessed")
    profiles = experiment["profiles"]
    if not isinstance(profiles, list) or not 1 <= len(profiles) <= 20:
        raise ValueError("requires 1..20 test profiles")
    ids: set[str] = set()
    outputs: list[dict[str, Any]] = []
    source_ids = {item["id"] for item in source_catalog["sources"]}
    for profile in profiles:
        result = _assess_profile(profile, source_ids)
        if result["id"] in ids:
            raise ValueError("falsification profile IDs must be unique")
        ids.add(result["id"])
        outputs.append(result)
    return {
        "schemaVersion": RESULT_SCHEMA,
        "kind": "synthetic_falsification_demo",
        "inputSha256": hashlib.sha256(raw).hexdigest(),
        "sourceCatalogSha256": hashlib.sha256(sources_raw).hexdigest(),
        "statisticalMethod": (
            "Bonferroni simultaneous Wilson intervals for two independent "
            "binomial proportions; conservative difference interval"
        ),
        "limitations": (
            "Synthetic i.i.d. Bernoulli trials ONLY. No physical measurement, "
            "paired or clustered QEC analysis, full randomized benchmarking "
            "fit, QV certification or multiplicity-adjusted exploratory sensitivity."
        ),
        "measurementVerified": False,
        "scientificReplication": False,
        "hardwareExecuted": False,
        "profiles": outputs,
    }
