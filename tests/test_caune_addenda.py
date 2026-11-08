"""Synthetic fixtures: deduplicated author mean times and stability-9 LEP."""
from __future__ import annotations

import pytest

from qfabric.caune_addenda import (
    ALREADY_RECOMPUTED,
    MEAN_ROUNDS,
    SHA256,
    STABILITY_ROUNDS,
    audit_additional_summaries,
)


def _mean() -> bytes:
    lines = ["    time (us)       err"]
    for n in MEAN_ROUNDS:
        mean = ALREADY_RECOMPUTED.get(n, 0.4 + n / 100)
        lines.append(f"{n} {mean:.6f} 0.001")
    return ("\n".join(lines) + "\n").encode()


def _stability() -> bytes:
    lines = ["       lep       std"]
    for n in STABILITY_ROUNDS:
        lines.append(f"{n} {0.41 - n / 1000:.5f} 0.00154")
    return ("\n".join(lines) + "\n").encode()


def test_overlap_is_validation_only_not_extra_data() -> None:
    report = audit_additional_summaries(_mean(), _stability(), enforce_pin=False)
    timing = report["meanDecodingTime"]
    assert timing["sourceRoundCount"] == 12
    assert len(timing["alreadyRecomputedOverlap"]) == 3
    assert [row["rounds"] for row in timing["alreadyRecomputedOverlap"]] == [9, 17, 25]
    assert len(timing["additionalRoundSummaries"]) == 9
    assert report["stability9Mwpm"]["sourceRoundCount"] == 12
    assert report["stability9Mwpm"]["experiment"] == (
        "stability_9_per_filename_not_stability_8"
    )
    assert report["stability9Mwpm"]["directComparisonToStability8Permitted"] is False
    assert report["independentHardwareMeasurementPerformed"] is False
    assert all(len(sha) == 64 for sha in SHA256.values())


def test_pinned_original_filenames_check_independently() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        audit_additional_summaries(_mean(), _stability())


def test_existing_mean_mismatch_fails_and_nonduplicate_rounds_survive() -> None:
    bogus = _mean().replace(b"9 0.483114", b"9 0.482114", 1)
    with pytest.raises(ValueError, match="300k"):
        audit_additional_summaries(bogus, _stability(), enforce_pin=False)


@pytest.mark.parametrize("bad", [
    b"bad header\n5 .40 .001\n",
    b"lep std\n5 NaN .001\n",
    b"lep std\n5 0.4 inf\n",
    b"lep std\n5 -0.5 .001\n",
    b"lep std\n5 .40 -.001\n",
    b"lep std\n5 .40 .001\n5 .39 .001\n",
    b"lep std\n27 .40 .001\n25 .39 .001\n",
    b"lep std\n4 .40 .001\n",
])
def test_untrusted_stability9_summary_rejects_invalid_table(bad: bytes) -> None:
    with pytest.raises(ValueError):
        audit_additional_summaries(_mean(), bad, enforce_pin=False, enforce_complete=False)


def test_missing_round_fails_under_complete_coverage_rule() -> None:
    with pytest.raises(ValueError, match="incomplete"):
        audit_additional_summaries(_mean(), b"lep std\n5 .4 .01\n", enforce_pin=False)
