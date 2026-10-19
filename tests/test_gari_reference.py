"""Independent algebraic tests against Eq. (1)-(7) of Maan et al. 2026.

These deliberately tiny matrices are synthetic, not the paper's BB code.
"""

from __future__ import annotations

from itertools import product
from pathlib import Path

import pytest

from qfabric.gari_evidence import SOURCE_BLOB_SHA1, parse_author_si1000_csv
from qfabric.gari_reference import (
    bpt_efficiency,
    build_gari_reference,
    four_cycles,
    per_round_logical_error_rate,
)

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "data/reference/gari_nms_si1000_upstream.csv"


def _toy():
    # Two detector rows in each basis, two single-type columns per basis,
    # two Y errors with X syndromes matching the first DX column.
    return build_gari_reference(
        dx=[[1, 1], [1, 0]],
        dz=[[1, 0], [1, 1]],
        y_x=[[1, 1], [1, 1]],
        y_z=[[1, 0], [1, 1]],
    )


def test_gari_reference_eq1_to_eq6_syndrome_equivalence_for_all_errors() -> None:
    ref = _toy()
    assert ref.original_width == 6
    assert len(ref.original) == 4
    assert len(ref.original[0]) == 6
    assert len(ref.augmented) == 8
    assert len(ref.augmented[0]) == 10
    assert ref.ux_index == (0, 0)
    assert ref.vz_index == (0, 1)
    assert ref.assert_equivalent() == 64


def test_gari_removes_y_biclique_four_cycles_in_small_synthetic_example() -> None:
    ref = _toy()
    assert four_cycles(ref.original) > four_cycles(ref.augmented)
    # The bottom U/V equality-check block has no 4 cycles, as in Table 1.
    assert four_cycles(ref.augmented[4:]) == 0


def test_lift_equation3_handles_y_correlations_xor() -> None:
    ref = _toy()
    # eZ=00, eX=00, eY=11: both Y columns map to DX col 0,
    # so the new eZ variable parity cancels, while eX tilde is 11.
    lifted = ref.lift((0, 0, 0, 0, 1, 1))
    assert lifted == (0, 0, 0, 0, 1, 1, 0, 0, 1, 1)


@pytest.mark.parametrize(
    ("dx", "dz", "yx", "yz"),
    [
        ([[1, 1], [1, 1]], [[1, 0], [1, 1]], [[1], [1]], [[1], [1]]),
        ([[1, 0], [0, 1]], [[1, 0], [0, 1]], [[1], [1]], [[1], [1]]),
        ([[1, 0], [0, 1]], [[1, 0], [0, 1]], [[1], [0]], [[1], [1]]),
        ([[1, 0], [0, 1]], [[1, 0], [0, 1]], [[True], [0]], [[1], [1]]),
    ],
)
def test_gari_refuses_violated_paper_matrix_assumptions(dx, dz, yx, yz) -> None:
    with pytest.raises((ValueError, TypeError)):
        build_gari_reference(dx, dz, yx, yz)


def test_exhaustive_model_uses_both_observable_types_and_bounds() -> None:
    ref = _toy()
    for bits in product((0, 1), repeat=6):
        ref.lift(bits)
    with pytest.raises(ValueError):
        ref.lift((True,) + (0,) * 5)


@pytest.mark.parametrize(
    ("n", "k", "d", "expected"),
    [(72, 12, 6, 6.0), (90, 8, 10, 800 / 90), (144, 12, 12, 12.0)],
)
def test_bpt_axis_matches_paper_figures(n: int, k: int, d: int, expected: float) -> None:
    assert bpt_efficiency(n, k, d) == pytest.approx(expected)


def test_per_round_rate_eq7_is_stable_at_very_low_error_rate() -> None:
    assert per_round_logical_error_rate(0, 100, 12) == 0.0
    assert per_round_logical_error_rate(10, 100, 1) == pytest.approx(0.1)
    assert per_round_logical_error_rate(1, 10**12, 12) == pytest.approx(
        1 / (12 * 10**12), rel=1e-8
    )
    assert per_round_logical_error_rate(50, 100, 12) == 0.5


@pytest.mark.parametrize(
    ("failures", "samples", "rounds"),
    [(0, 0, 12), (-1, 100, 12), (60, 100, 12), (1, 10, 0), (True, 100, 1)],
)
def test_per_round_rejects_malformed_counts(failures, samples, rounds) -> None:
    with pytest.raises((ValueError, TypeError)):
        per_round_logical_error_rate(failures, samples, rounds)


def test_authors_csv_pinned_blob_and_per_round_rates_without_running_decoder() -> None:
    report = parse_author_si1000_csv(UPSTREAM.read_bytes())
    assert report["upstreamGitBlobSha1"] == SOURCE_BLOB_SHA1
    assert report["upstreamBlobMatched"] is True
    assert len(report["records"]) == 15
    first = report["records"][0]
    assert (first["shots"], first["errors"], first["codeDistance"]) == (131072, 114, 6)
    assert first["physicalErrorProbability"] == 0.001
    assert first["perRoundLERFromPublishedCounts"] < first["failureRatioFromPublishedCounts"]
    assert report["authorCodeExecuted"] is False
    assert report["newSimulationPerformed"] is False
    assert report["paperNumericsFullyReproduced"] is False
    assert report["fpgaMeasured"] is False


def test_upstream_author_blob_change_is_detected() -> None:
    raw = UPSTREAM.read_bytes()
    edited = raw.replace(b"131072", b"131073", 1)
    assert edited != raw
    with pytest.raises(ValueError, match="pinned Git blob"):
        parse_author_si1000_csv(edited)


def test_upstream_csv_rejects_nan_and_invalid_scientific_counts() -> None:
    raw = UPSTREAM.read_bytes()
    edited = raw.replace(b"131072", b"0", 1)
    with pytest.raises(ValueError):
        parse_author_si1000_csv(edited, enforce_upstream_blob=False)
    edited = raw.replace(b"    4.00", b"     nan", 1)
    with pytest.raises(ValueError):
        parse_author_si1000_csv(edited, enforce_upstream_blob=False)
