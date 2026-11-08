"""Strict, offline audit of Caune et al. (2024) author LEP figure tables.

These are author-reported aggregate logical-error probabilities, not
independent QFabric QPU results, decoder executions or raw binary shot records.
Never infer paired standard errors, statistical significance, real-time reset
performance or a causal reset effect from aggregate LEP tables alone.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from typing import Any

SCHEMA = "qfabric-caune-2024-lep-figure-audit/1"
PAPER_URL = "https://arxiv.org/abs/2410.05202"
MAX_BYTES_PER_FILE = 4096
MAIN_ROUNDS = tuple(range(5, 26, 2))
RESET_ROUNDS = (7, 11, 15, 19, 23)
SOURCE_SPECS = {
    "lep_fpga.txt": {
        "sha256": "9e3893c60ef1302d958d5752762089480beae65e5aed0f522af489b8917e7c36",
        "method": "real_time_fpga_collision_clustering",
        "figure": "main_figure_3a",
        "condition": "no_mid_circuit_reset",
        "expectedRounds": MAIN_ROUNDS,
        "errorBarDefinition": "author_figure_3a_standard_error_of_mean",
    },
    "lep_mwpm.txt": {
        "sha256": "2243153c8564f5441fcfe1cefcd40ba2bd51c3c75f3841f70f92a5e63539aea7",
        "method": "offline_mwpm_hard_readout",
        "figure": "main_figure_3a",
        "condition": "no_mid_circuit_reset",
        "expectedRounds": MAIN_ROUNDS,
        "errorBarDefinition": "author_figure_3a_standard_error_of_mean",
    },
    "lep_belief_matching.txt": {
        "sha256": "3c28afe0f1970aa829089f1543dcf22babbe1c6cb4731835cc87c006b52c28b4",
        "method": "offline_belief_matching_hard_readout",
        "figure": "main_figure_3a",
        "condition": "no_mid_circuit_reset",
        "expectedRounds": MAIN_ROUNDS,
        "errorBarDefinition": "author_figure_3a_standard_error_of_mean",
    },
    "lep_mwpm_soft_info_pairwise_correlation_graph.txt": {
        "sha256": "106be5ff47bcb3e7474932461b2886371a7cdf2ea60783100856ba7777fb85f8",
        "method": "offline_mwpm_soft_info_pairwise_correlation",
        "figure": "main_figure_3a",
        "condition": "no_mid_circuit_reset",
        "expectedRounds": MAIN_ROUNDS,
        "errorBarDefinition": "author_figure_3a_standard_error_of_mean",
    },
    "lep_mwpm_soft_info_pairwise_correlation_graph_with_resets.txt": {
        "sha256": "95dba7ac221519828d942c203f51d2e0b7a150b81fed337c9c4bd357a4c66164",
        "method": "offline_mwpm_soft_info_pairwise_correlation",
        "figure": "supplementary_figure_6",
        "condition": "unconditional_ancilla_resets",
        "expectedRounds": RESET_ROUNDS,
        "errorBarDefinition": "author_supplementary_figure_6_standard_deviation_of_mean_values",
    },
}


def parse_lep_table(
    raw: bytes, filename: str, *, enforce_pin: bool = True,
    enforce_complete: bool = True,
) -> dict[str, Any]:
    """Read original whitespace-indexed LEP + err rows without author code."""
    if filename not in SOURCE_SPECS:
        raise ValueError("unrecognized author source name")
    spec = SOURCE_SPECS[filename]
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES_PER_FILE:
        raise ValueError("input must be bounded nonempty original bytes")
    digest = hashlib.sha256(raw).hexdigest()
    if enforce_pin and digest != spec["sha256"]:
        raise ValueError("SHA-256 differs from pinned user-uploaded file")
    lines = [line.split() for line in raw.decode("utf-8", errors="strict").splitlines()
             if line.strip()]
    if not lines or lines[0] != ["lep", "err"]:
        raise ValueError("unexpected original LEP/err table header")
    if len(lines) < 2 or len(lines) > 40:
        raise ValueError("invalid number of rows")
    rows = []
    seen: set[int] = set()
    for line in lines[1:]:
        if len(line) != 3 or not line[0].isascii() or not line[0].isdecimal():
            raise ValueError("expected three columns: integer round, LEP, err")
        rounds = int(line[0])
        if rounds in seen or rounds not in spec["expectedRounds"]:
            raise ValueError("duplicate or out-of-range decoding round")
        if rows and rounds <= rows[-1]["rounds"]:
            raise ValueError("decoding rounds are not strictly increasing")
        seen.add(rounds)
        try:
            lep = float(line[1])
            error = float(line[2])
        except ValueError as exc:
            raise ValueError("invalid numeric LEP or uncertainty") from exc
        if (not math.isfinite(lep) or not math.isfinite(error)
                or not 0 <= lep <= 1 or not 0 < error <= 1):
            raise ValueError("LEP or error bar outside finite probability bounds")
        rows.append({"rounds": rounds, "lep": lep, "reportedError": error})
    expected = tuple(spec["expectedRounds"])
    if enforce_complete and tuple(row["rounds"] for row in rows) != expected:
        raise ValueError("missing decoding-round observations")
    return {
        "filename": filename, "sourceSha256OfUserBytes": digest,
        "method": spec["method"], "figure": spec["figure"],
        "condition": spec["condition"], "reportedErrorMeaning": spec["errorBarDefinition"],
        "observations": rows, "rows": len(rows),
        "authorHardwareExperimentReprocessed": True,
        "originalShotRecordsAvailable": False,
    }


def audit_caune_lep_bundle(
    sources: Mapping[str, bytes], *, enforce_pin: bool = True,
    enforce_complete: bool = True,
) -> dict[str, Any]:
    """Only match declared round indices; never manufacture unobserved rows."""
    if set(sources) != set(SOURCE_SPECS):
        raise ValueError("all five specifically named author tables required")
    tables = {
        name: parse_lep_table(
            sources[name], name, enforce_pin=enforce_pin, enforce_complete=enforce_complete,
        )
        for name in SOURCE_SPECS
    }
    by_name = {
        name: {point["rounds"]: point for point in row["observations"]}
        for name, row in tables.items()
    }
    fpga = by_name["lep_fpga.txt"]
    soft = by_name["lep_mwpm_soft_info_pairwise_correlation_graph.txt"]
    reset = by_name["lep_mwpm_soft_info_pairwise_correlation_graph_with_resets.txt"]
    hard_comparison = []
    for rounds in sorted(set(fpga) & set(soft)):
        baseline, candidate = fpga[rounds]["lep"], soft[rounds]["lep"]
        hard_comparison.append({
            "rounds": rounds, "fpgaLep": baseline,
            "offlineSoftCorrelationLep": candidate,
            "absoluteReductionProbabilityPoints": baseline - candidate,
            "relativeReductionFraction": (baseline - candidate) / baseline if baseline else None,
            "independentSignificanceEstablished": False,
            "matchedPerShotOutcomesAvailable": False,
        })
    reset_comparison = []
    for rounds in sorted(set(soft) & set(reset)):
        no_reset, with_reset = soft[rounds]["lep"], reset[rounds]["lep"]
        reset_comparison.append({
            "rounds": rounds, "noResetLepFromMainFigure3a": no_reset,
            "withResetLepFromSupplementaryFigure6": with_reset,
            "absoluteReductionProbabilityPoints": no_reset - with_reset,
            "relativeReductionFraction": (
                (no_reset - with_reset) / no_reset if no_reset else None
            ),
            "matchedExperimentalSessionConfirmed": False,
            "causalResetImprovementEstablished": False,
        })
    if enforce_complete and (len(hard_comparison) != 11 or len(reset_comparison) != 5):
        raise ValueError("unexpected overlap between cited experimental series")
    return {
        "schemaVersion": SCHEMA,
        "paperUrl": PAPER_URL,
        "inputStatus": "user_uploaded_author_aggregate_figure_tables",
        "upstreamZenodoChecksumsAuthenticated": False,
        "sourceFileRedistributionRightsVerified": False,
        "tables": tables,
        "fpgaVersusOfflineSoftComparison": hard_comparison,
        "resetVersusNonresetDescriptiveComparison": reset_comparison,
        "fpgaAllRoundsAboveSoftLep": all(
            row["absoluteReductionProbabilityPoints"] > 0 for row in hard_comparison
        ),
        "resetsAllAvailableRoundsBelowNoResetLep": all(
            row["absoluteReductionProbabilityPoints"] > 0 for row in reset_comparison
        ),
        "noNewQuantumMeasurements": True,
        "qfabricDecoderExecuted": False,
        "resetConditionEverTestedOnRealTimeFpgaInPaper": False,
        "observationalCausalityOrIndependentStatisticalSignificanceClaimed": False,
        "notes": [
            "Four Figure 3a series are FPGA real-time vs offline postprocessing, not four hardware decoder implementations.",
            "The fifth reset series has only 7/11/15/19/23 rounds and was NOT evaluated by the original real-time FPGA decoder.",
            "Source error bars may be reported SEM or SD-of-means according to figure; no joint outcomes or covariance provided for paired differences.",
            "Supplementary Figure 6 includes no-reset comparison; exact matching of acquisition session for this uploaded Fig. 3a no-reset series is unverified.",
            "Nonmonotonic LEP at some rounds must remain visible; no monotonic or quantum advantage claim is implied.",
        ],
    }
