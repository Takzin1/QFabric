"""Comparisons state what they test; incomparable observations are refused."""

import pytest

from qfabric.research import COMPARISON_TESTS
from qfabric.research.comparability import (
    IncomparableObservations,
    Observation,
    assess_comparison,
)


def _lep(**overrides) -> Observation:
    fields = {
        "label": "series", "quantity": "logical_error_probability", "unit": "fraction",
        "provenance": "measured", "aggregation": "per_shot", "experiment": "stability-8",
        "conditions": {"decoder": "fpga", "reset": "none"}, "session": "day-1",
    }
    return Observation(**{**fields, **overrides})


def test_same_session_single_varied_condition_is_a_hypothesis_test() -> None:
    verdict = assess_comparison(
        _lep(), _lep(conditions={"decoder": "offline_mwpm", "reset": "none"}),
        varied=frozenset({"decoder"}),
    )
    assert verdict == {
        "comparable": True, "tests": "scientific_hypothesis", "inference": "same_session",
        "varied": ["decoder"], "notes": [],
    }


@pytest.mark.parametrize("first, second, expected", [
    ("synthetic", "synthetic", "software_correctness"),
    ("measured", "simulated", "experimental_validity"),
    ("simulated", "simulated", "scientific_hypothesis"),
])
def test_every_allowed_comparison_names_what_it_tests(first, second, expected) -> None:
    verdict = assess_comparison(
        _lep(provenance=first),
        _lep(provenance=second, conditions={"decoder": "other", "reset": "none"}),
        varied=frozenset({"decoder"}),
    )
    assert verdict["tests"] == expected and expected in COMPARISON_TESTS


@pytest.mark.parametrize("change, reason", [
    ({"experiment": "stability-9"}, "experiment differs"),
    ({"unit": "percent"}, "unit differs"),
    ({"quantity": "defect_rate"}, "quantity differs"),
    ({"aggregation": "figure_aggregate"}, "aggregation differs"),
    ({"provenance": "synthetic"}, "cannot be compared"),
    ({"provenance": "inferred"}, "cannot be compared"),
    ({"conditions": {"decoder": "offline", "reset": "unconditional"}}, "undeclared differing"),
    ({"conditions": {"decoder": "offline"}}, "different condition names"),
    ({"conditions": {"decoder": "fpga", "reset": "none"}}, "do not differ"),
])
def test_scientifically_incomparable_observations_are_refused(change, reason) -> None:
    other = {"conditions": {"decoder": "offline", "reset": "none"}, **change}
    with pytest.raises(IncomparableObservations, match=reason) as caught:
        assess_comparison(_lep(), _lep(**other), varied=frozenset({"decoder"}))
    assert caught.value.reasons


def test_all_reasons_are_reported_together() -> None:
    with pytest.raises(IncomparableObservations) as caught:
        assess_comparison(
            _lep(), _lep(unit="percent", experiment="stability-9", provenance="synthetic"),
            varied=frozenset({"decoder"}),
        )
    assert len(caught.value.reasons) == 4


def test_cross_session_or_aggregate_comparisons_are_descriptive_only() -> None:
    other = {"conditions": {"decoder": "fpga", "reset": "unconditional"}}
    for change in ({"session": "day-2"}, {"session": None}):
        verdict = assess_comparison(_lep(), _lep(**other, **change), varied=frozenset({"reset"}))
        assert verdict["inference"] == "descriptive_only" and "drift" in verdict["notes"][0]
    verdict = assess_comparison(
        _lep(aggregation="figure_aggregate"), _lep(aggregation="figure_aggregate", **other),
        varied=frozenset({"reset"}),
    )
    assert verdict["inference"] == "descriptive_only" and "covariance" in verdict["notes"][0]


@pytest.mark.parametrize("fields", [
    {"provenance": "authenticated"}, {"aggregation": "raw"}, {"label": ""},
    {"conditions": {"decoder": 3}}, {"conditions": {str(i): "x" for i in range(17)}},
    {"session": ""},
])
def test_observation_rejects_unknown_labels(fields) -> None:
    with pytest.raises(ValueError):
        _lep(**fields)


def test_varied_conditions_must_be_declared_up_front() -> None:
    for varied in (frozenset(), {"decoder"}, None):
        with pytest.raises(ValueError):
            assess_comparison(_lep(), _lep(), varied=varied)
