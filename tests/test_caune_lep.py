"""Independent synthetic fixtures for Caune's five author LEP tables.

No third-party experimental LEP values are copied into this test suite.
"""
from __future__ import annotations

import pytest

from qfabric.caune_lep import (
    MAIN_ROUNDS,
    RESET_ROUNDS,
    SOURCE_SPECS,
    audit_caune_lep_bundle,
    parse_lep_table,
)


def _fixture(filename: str) -> bytes:
    rounds = SOURCE_SPECS[filename]["expectedRounds"]
    # A generated, demonstrably synthetic LEP profile. Not Caune's results.
    lines = ["         lep       err"]
    for index, n in enumerate(rounds):
        amount = 0.35 - index * 0.007
        if filename == "lep_mwpm_soft_info_pairwise_correlation_graph.txt":
            amount -= 0.04
        if filename.endswith("_with_resets.txt"):
            amount -= 0.06
        lines.append(f"{n}  {amount:.6f}  0.001200")
    return ("\n".join(lines) + "\n").encode()


def _all_inputs() -> dict[str, bytes]:
    return {filename: _fixture(filename) for filename in SOURCE_SPECS}


def test_source_pins_and_exact_round_sets_are_separate() -> None:
    assert len(SOURCE_SPECS) == 5
    assert MAIN_ROUNDS == tuple(range(5, 26, 2))
    assert RESET_ROUNDS == (7, 11, 15, 19, 23)
    assert all(len(spec["sha256"]) == 64 for spec in SOURCE_SPECS.values())
    assert len(set(spec["sha256"] for spec in SOURCE_SPECS.values())) == 5
    for name in SOURCE_SPECS:
        observed = parse_lep_table(_fixture(name), name, enforce_pin=False)
        assert observed["rows"] == len(SOURCE_SPECS[name]["expectedRounds"])
        assert tuple(x["rounds"] for x in observed["observations"]) == tuple(
            SOURCE_SPECS[name]["expectedRounds"]
        )
        assert observed["originalShotRecordsAvailable"] is False
        with pytest.raises(ValueError, match="SHA-256"):
            parse_lep_table(_fixture(name), name, enforce_pin=True)


def test_synthetic_comparisons_do_not_claim_decoder_or_qpu_execution() -> None:
    report = audit_caune_lep_bundle(_all_inputs(), enforce_pin=False)
    assert len(report["fpgaVersusOfflineSoftComparison"]) == 11
    assert len(report["resetVersusNonresetDescriptiveComparison"]) == 5
    assert report["noNewQuantumMeasurements"] is True
    assert report["qfabricDecoderExecuted"] is False
    assert report["resetConditionEverTestedOnRealTimeFpgaInPaper"] is False
    assert report["observationalCausalityOrIndependentStatisticalSignificanceClaimed"] is False
    assert all(row["independentSignificanceEstablished"] is False
               for row in report["fpgaVersusOfflineSoftComparison"])
    assert all(row["causalResetImprovementEstablished"] is False
               for row in report["resetVersusNonresetDescriptiveComparison"])
    assert report["tables"]["lep_fpga.txt"]["method"] == (
        "real_time_fpga_collision_clustering"
    )
    assert report["tables"]["lep_mwpm.txt"]["method"] == (
        "offline_mwpm_hard_readout"
    )


@pytest.mark.parametrize("bad", [
    b"not_a_header\n5 0.2 0.001\n",
    b"lep err\n5 nan 0.001\n",
    b"lep err\n5 0.3 inf\n",
    b"lep err\n5 -0.3 0.001\n",
    b"lep err\n5 1.2 0.001\n",
    b"lep err\n5 0.3 -0.001\n",
    b"lep err\n5 0.3 0\n",
    b"lep err\n5 0.3 0.001 extra\n",
    b"lep err\n5.0 0.3 0.001\n",
    b"lep err\n5 0.3 0.001\n5 0.2 0.001\n",
    b"lep err\n7 0.2 0.001\n5 0.3 0.001\n",
    b"lep err\n4 0.2 0.001\n",
    b"lep err\n9 0.2 0.001\n",  # wrong for reset dataset
])
def test_invalid_or_nonfactual_uploaded_aggregate_tables_are_rejected(bad: bytes) -> None:
    filename = ("lep_mwpm_soft_info_pairwise_correlation_graph_with_resets.txt"
                if b"\n9 " in bad else "lep_fpga.txt")
    with pytest.raises((ValueError, TypeError)):
        parse_lep_table(bad, filename, enforce_pin=False, enforce_complete=False)


def test_five_files_required_no_filename_swap_and_missing_rounds_rejected() -> None:
    files = _all_inputs()
    with pytest.raises(ValueError, match="all five"):
        audit_caune_lep_bundle({k: v for k, v in files.items() if k != "lep_fpga.txt"},
                               enforce_pin=False)
    with pytest.raises(ValueError, match="missing"):
        parse_lep_table(
            _fixture("lep_fpga.txt").replace(b"25  ", b"26  ", 1),
            "lep_fpga.txt", enforce_pin=False,
        )
    with pytest.raises(ValueError, match="out-of-range"):
        parse_lep_table(
            _fixture("lep_fpga.txt").replace(b"25  ", b"26  ", 1),
            "lep_fpga.txt", enforce_pin=False, enforce_complete=False,
        )
    with pytest.raises(ValueError, match="SHA-256"):
        parse_lep_table(
            _fixture("lep_fpga.txt"),
            "lep_mwpm.txt", enforce_pin=True,
        )


def test_nonmonotonic_source_lep_is_not_silently_smoothed_or_rejected() -> None:
    raw = _fixture("lep_fpga.txt")
    assert b"21  " in raw and b"23  " in raw
    raw = raw.replace(b"23  0.287000", b"23  0.350000", 1)
    parsed = parse_lep_table(raw, "lep_fpga.txt", enforce_pin=False)
    assert parsed["observations"][-2]["lep"] == pytest.approx(0.35)
    assert parsed["observations"][-3]["lep"] < parsed["observations"][-2]["lep"]
