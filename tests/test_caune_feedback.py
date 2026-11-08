"""Synthetic tests for historical Caune 2024 figure parsers (no raw data committed)."""
from __future__ import annotations

import math

import pytest

from qfabric.caune_feedback import (
    PAPER_T1_US,
    SOURCE_SHA256,
    audit_caune_feedback_figures,
    audit_fig4b,
    audit_si_density,
    audit_si_gamma,
    audit_si_t1,
)


def _fig4b() -> bytes:
    lines = [
        "rounds,control_system_logic,control_system_logic_std,decoding_time,"
        "decoding_time_std,delay_measured_by_qubit,delay_measured_by_qubit_std",
    ]
    for n in range(2, 10):
        lines.append(f"{n},{float(3000+n*1000)},500,{float(n*700)},400,{n+2}.5,0.6")
    return ("\n".join(lines) + "\n").encode()


def _kde() -> bytes:
    lines = ["rounds,times,gaussian_kde_probability"]
    for n in range(2, 10):
        for i in range(30 if n == 2 else 50):
            lines.append(f"{n},{2+i*0.1},{math.exp(-i*0.1):.12g}")
    return ("\n".join(lines) + "\n").encode()


def _gamma() -> bytes:
    lines = ["rounds,k,theta"]
    lines.extend(f"{n},{20+n},0.2" for n in range(2, 10))
    return ("\n".join(lines) + "\n").encode()


def _t1() -> bytes:
    lines = [",delay_time,excited_state_population"]
    for index in range(13):
        time = index * 0.8
        measured = 0.85 * math.exp(-time / 13) + 0.08
        lines.append(f"{index},{time},{measured:.12f}+/-0.005")
    return ("\n".join(lines) + "\n").encode()


def test_fig4b_unit_conversion_and_nondecoding_components() -> None:
    rows = audit_fig4b(_fig4b(), enforce_pin=False)["entries"]
    assert len(rows) == 8
    assert rows[0]["controlSystemTotalUsInterpretedFromPaper"] == 5
    assert rows[0]["fpgaDecoderUs"] == 1.4
    assert rows[0]["differenceNonDecoderUs"] == pytest.approx(3.6)
    assert rows[0]["qubitInferredDelayUs"] == 4.5
    assert all(r["differenceNonDecoderUs"] >= 0 for r in rows)


def test_gamma_appendix_e13_matches_independent_expression() -> None:
    data = audit_si_gamma(_gamma(), enforce_pin=False)
    assert data["t1ForE13Us"] == PAPER_T1_US
    for entry in data["entries"]:
        k, theta = entry["gammaShapeK"], entry["gammaScaleThetaUs"]
        assert entry["gammaMeanUs"] == pytest.approx(k * theta)
        assert entry["gammaStdUs"] == pytest.approx(math.sqrt(k) * theta)
        assert entry["t1EffectiveUsByAppendixE13"] == pytest.approx(
            -PAPER_T1_US * math.log((1 + theta / PAPER_T1_US) ** (-k))
        )
        assert 0 < entry["t1EstimatorRelativeBias"] < 0.03


def test_kde_is_truncated_plot_curve_not_samples_or_normalized_pdf() -> None:
    data = audit_si_density(_kde(), enforce_pin=False)
    assert data["rows"] == 380
    assert [r["samples"] for r in data["series"]] == [30, 50, 50, 50, 50, 50, 50, 50]
    assert data["densityWindowNotRequiredToIntegrateToOne"]
    assert data["series"][0]["sampleWindowTrapezoidArea"] > 0


def test_t1_independent_weighted_fit_recovers_known_synthetic_lifetime() -> None:
    data = audit_si_t1(_t1(), enforce_pin=False)
    fitted = data["fit"]
    assert fitted["fittedT1Us"] == pytest.approx(13, abs=0.002)
    assert fitted["fittedAmplitudeA"] == pytest.approx(0.85, abs=0.001)
    assert fitted["fittedOffsetB"] == pytest.approx(0.08, abs=0.001)
    assert fitted["degreesOfFreedom"] == 10
    assert fitted["weightedChiSquared"] < 1e-10


def test_combined_figures_never_claim_new_measurements_or_authoritative_checksums() -> None:
    result = audit_caune_feedback_figures(
        _fig4b(), _kde(), _gamma(), _t1(), enforce_pin=False,
    )
    assert result["physicalHardwareExecutedByQFabric"] is False
    assert result["originalQuantumMeasurementsReacquired"] is False
    assert result["paperFullFeedbackExperimentReproduced"] is False
    assert result["rawDataRedistributionRightsVerified"] is False
    assert len(result["gammaVersusFpgaMean"]) == 8
    assert len(SOURCE_SHA256) == 4
    assert all(len(v) == 64 for v in SOURCE_SHA256.values())


def test_raw_source_pin_rejects_unrelated_fixture() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        audit_fig4b(_fig4b())
    with pytest.raises(ValueError, match="SHA-256"):
        audit_si_t1(_t1())


@pytest.mark.parametrize(("source", "old", "new"), [
    ("fig4b", b"5000.0", b"0"),
    ("fig4b", b"1.4", b"nan"),
    ("gamma", b"0.2", b"-0.2"),
    ("gamma", b"0.2", b"nan"),
    ("kde", b"2,2.0,", b"2,NaN,"),
    ("kde", b"2,2.0,", b"2,-1,"),
    ("t1", b"+/-0.005", b"+/-0"),
    ("t1", b"+/-0.005", b""),
])
def test_malformed_values_fail_closed(source: str, old: bytes, new: bytes) -> None:
    inputs = {
        "fig4b": (audit_fig4b, _fig4b()),
        "gamma": (audit_si_gamma, _gamma()),
        "kde": (audit_si_density, _kde()),
        "t1": (audit_si_t1, _t1()),
    }
    fn, raw = inputs[source]
    if old not in raw:
        # The test is about a real schema value, not a no-op replacement.
        pytest.fail("test fixture replacement did not match")
    with pytest.raises((ValueError, TypeError)):
        fn(raw.replace(old, new, 1), enforce_pin=False)


def test_schema_and_round_alignment_are_required() -> None:
    bad_gamma = _gamma().replace(b"2,22", b"3,22", 1)
    with pytest.raises(ValueError, match="duplicate"):
        audit_si_gamma(bad_gamma, enforce_pin=False)
    bad_figure = _fig4b().replace(
        b"control_system_logic_std", b"control_system_logic_wrong", 1
    )
    with pytest.raises(ValueError, match="schema"):
        audit_fig4b(bad_figure, enforce_pin=False)
    bad_kde = _kde().replace(b"2,2.0", b"2,2.1", 1)
    with pytest.raises(ValueError, match="strictly increasing"):
        audit_si_density(bad_kde, enforce_pin=False)


def test_incomplete_traces_are_rejected_in_default_audit() -> None:
    gamma_short = _gamma().replace(b"9,29,0.2\n", b"")
    with pytest.raises(ValueError, match="incomplete"):
        audit_si_gamma(gamma_short, enforce_pin=False)
    t1_short = _t1().rsplit(b"\n", 2)[0] + b"\n"
    with pytest.raises(ValueError, match="incomplete"):
        audit_si_t1(t1_short, enforce_pin=False)
