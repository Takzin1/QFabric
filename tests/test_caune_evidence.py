"""Synthetic fixtures for a strict reader of Caune 2024 user-supplied data.

Never mistake small in-repo strings for author hardware measurements.
"""
from __future__ import annotations

import pytest

from qfabric.caune_evidence import (
    EXPECTED_SHA256,
    audit_decoder_timings,
    audit_defect_rates,
    audit_uploaded_caune_bundle,
)


def _timing_csv() -> bytes:
    # Exactly 156.25 MHz: 9 cycles / (156.25 * 9) = 0.0064 µs.
    lines = ["rounds,cycles,time_per_round"]
    for rounds in (9, 17, 25):
        for cycles in (rounds * 100, rounds * 250):
            lines.append(f"{rounds},{float(cycles)},"
                         f"{cycles / 156.25 / rounds!r}")
    return ("\n".join(lines) + "\n").encode()


def _defect_text(stability9: bool = False) -> bytes:
    if stability9:
        lines = [" round rate_1 rate_2 rate_3 rate_4"]
    else:
        lines = [" round Qubit 50 Qubit 52 Qubit 36 Qubit 38"]
    for round_no in range(1, (27 if stability9 else 25) + 1):
        lines.append(f"{round_no} 0.31 0.32 0.28 0.30")
    return ("\n".join(lines) + "\n").encode()


def test_synthetic_timing_groups_are_clock_consistent() -> None:
    report = audit_decoder_timings(
        _timing_csv(), enforce_pin=False, enforce_complete=False,
    )
    assert report["rowCount"] == 6
    assert [entry["rounds"] for entry in report["groups"]] == [9, 17, 25]
    assert all(entry["records"] == 2 for entry in report["groups"])
    assert all(entry["meanUsPerRound"] == pytest.approx(1.12) for entry in report["groups"])
    assert all(entry["repetitionFractionAbove1UsPerRound"] == 0.5
               for entry in report["groups"])
    assert all(entry["p99UsPerRound"] == 1.6 for entry in report["groups"])


def test_uploaded_raw_byte_pins_are_separate_from_synthetic_fixtures() -> None:
    assert all(len(value) == 64 for value in EXPECTED_SHA256.values())
    with pytest.raises(ValueError, match="SHA-256"):
        audit_decoder_timings(_timing_csv(), enforce_pin=True, enforce_complete=False)
    with pytest.raises(ValueError, match="incomplete"):
        audit_decoder_timings(_timing_csv(), enforce_pin=False, enforce_complete=True)


@pytest.mark.parametrize("bad", [
    b"rounds,cycles,time_per_round\n9,100,0.1\n",
    b"rounds,cycles,time_per_round\n9,100.1,0.071111\n",
    b"rounds,cycles,time_per_round\n9,nan,0.1\n",
    b"rounds,cycles,time_per_round\n9,100,NaN\n",
    b"rounds,cycles,time_per_round\n9,100,inf\n",
    b"rounds,cycles,time_per_round\n0,100,0.64\n",
    b"rounds,cycles,time_per_round\n9,100,0.071111,extra\n",
    b"rounds,cycles,seconds\n9,100,1\n",
    b"rounds,cycles,time_per_round\n9,1,0\n",
])
def test_reject_malformed_timing_tables(bad: bytes) -> None:
    with pytest.raises((ValueError, TypeError)):
        audit_decoder_timings(bad, enforce_pin=False, enforce_complete=False)


def test_defect_25_has_named_qubits_27_row_table_is_unresolved() -> None:
    named = audit_defect_rates(
        _defect_text(), filename="defect_rates_per_round.txt",
        enforce_pin=False,
    )
    anonymous = audit_defect_rates(
        _defect_text(True), filename="defect_rates_per_round_stability_9.txt",
        enforce_pin=False,
    )
    assert named["rounds"] == 25
    assert named["figureAssociation"] == "figure_3b_stability_8"
    assert [s["label"] for s in named["series"]] == [
        "Qubit 50", "Qubit 52", "Qubit 36", "Qubit 38",
    ]
    assert anonymous["rounds"] == 27
    assert anonymous["figureAssociation"] == "UNRESOLVED"
    assert anonymous["series"][0]["label"] == "rate_1"


def test_no_hardware_or_upstream_authenticity_claims_from_fixture() -> None:
    report = audit_uploaded_caune_bundle(
        _timing_csv(), _defect_text(), _defect_text(True),
        enforce_pin=False, enforce_complete=False,
    )
    assert report["qfabricMeasurementsPerformed"] is False
    assert report["originalHardwareAccess"] is False
    assert report["upstreamDistributionAuthenticated"] is False
    assert report["redistributionLicenseVerified"] is False
    assert report["backlogObservedFromRawTimestamps"] is False


@pytest.mark.parametrize("needle,replacement", [
    (b"0.31", b"1.31"), (b"0.31", b"nan"), (b"0.31", b"-0.1"),
    (b"25 0.31", b"24 0.31"), (b"0.31 0.32", b"0.31"),
])
def test_reject_bad_defect_rates(needle: bytes, replacement: bytes) -> None:
    corrupted = _defect_text().replace(needle, replacement, 1)
    with pytest.raises(ValueError):
        audit_defect_rates(
            corrupted, filename="defect_rates_per_round.txt",
            enforce_pin=False,
        )


def test_reject_27_round_anonymous_data_mislabelled_as_25_round_qubit_series() -> None:
    with pytest.raises(ValueError):
        audit_defect_rates(
            _defect_text(True), filename="defect_rates_per_round.txt",
            enforce_pin=False,
        )
    with pytest.raises(ValueError):
        audit_defect_rates(
            _defect_text(), filename="unknown.txt", enforce_pin=False,
        )
