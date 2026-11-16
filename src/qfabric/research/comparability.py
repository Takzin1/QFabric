"""Decide whether two observations may be compared, and what that can show.

Scientifically incomparable observations are refused with the reasons stated;
a difference between them is not computed and then hedged afterwards.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from qfabric.research import PROVENANCE

AGGREGATION = ("per_shot", "per_repetition", "figure_aggregate", "model_parameter")
MAX_CONDITIONS = 16


class IncomparableObservations(ValueError):
    """Raised with every reason the two observations cannot be compared."""

    def __init__(self, reasons: list[str]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = tuple(reasons)


def _label(value: Any, name: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 120:
        raise ValueError(f"{name} must be a bounded nonempty label")
    return value


@dataclass(frozen=True, slots=True)
class Observation:
    """What was observed, in which experiment, under which declared conditions."""

    label: str
    quantity: str
    unit: str
    provenance: str
    aggregation: str
    experiment: str
    conditions: Mapping[str, str] = field(default_factory=dict)
    session: str | None = None

    def __post_init__(self) -> None:
        for name in ("label", "quantity", "unit", "experiment"):
            _label(getattr(self, name), name)
        if self.provenance not in PROVENANCE:
            raise ValueError(f"provenance must be one of {PROVENANCE}")
        if self.aggregation not in AGGREGATION:
            raise ValueError(f"aggregation must be one of {AGGREGATION}")
        if self.session is not None:
            _label(self.session, "session")
        if not isinstance(self.conditions, Mapping) or len(self.conditions) > MAX_CONDITIONS:
            raise ValueError("conditions must be a mapping of at most 16 entries")
        for key, value in self.conditions.items():
            _label(key, "condition name")
            _label(value, "condition value")
        object.__setattr__(self, "conditions", MappingProxyType(dict(self.conditions)))


def assess_comparison(
    first: Observation, second: Observation, *, varied: frozenset[str],
) -> dict[str, Any]:
    """Return what comparing the two can establish, or raise IncomparableObservations.

    ``varied`` is the pre-declared set of conditions the comparison is about.
    Any other condition that differs is a confound and causes a refusal.
    """
    if not isinstance(varied, frozenset) or not varied:
        raise ValueError("declare the varied condition(s) as a nonempty frozenset")
    reasons = [
        f"{name} differs: {getattr(first, name)!r} vs {getattr(second, name)!r}"
        for name in ("quantity", "unit", "aggregation", "experiment")
        if getattr(first, name) != getattr(second, name)
    ]
    pair = {first.provenance, second.provenance}
    if pair == {"synthetic"}:
        tests = "software_correctness"
    elif pair == {"measured", "simulated"}:
        tests = "experimental_validity"
    elif len(pair) == 1:
        tests = "scientific_hypothesis"
    else:
        tests = None
        reasons.append(
            f"provenance {first.provenance!r} cannot be compared with {second.provenance!r}"
        )
    if first.conditions.keys() != second.conditions.keys():
        reasons.append("the two observations declare different condition names")
    else:
        differing = {k for k in first.conditions if first.conditions[k] != second.conditions[k]}
        if differing - varied:
            reasons.append(f"undeclared differing condition(s): {sorted(differing - varied)}")
        if varied - differing:
            reasons.append(f"declared varied condition(s) do not differ: {sorted(varied - differing)}")
    if reasons:
        raise IncomparableObservations(reasons)

    notes: list[str] = []
    if first.aggregation in {"figure_aggregate", "model_parameter"}:
        notes.append("aggregates carry no shot counts or covariance")
    if "inferred" in pair:
        notes.append("inferred quantities inherit the assumptions of the model that produced them")
    if first.session is None or first.session != second.session:
        notes.append("acquisition sessions differ or are undeclared, so drift is not controlled")
    return {
        "comparable": True,
        "tests": tests,
        "inference": "descriptive_only" if notes else "same_session",
        "varied": sorted(varied),
        "notes": notes,
    }
