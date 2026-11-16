"""Small classical reference decoders and an exhaustive oracle to judge them.

Scope: binary linear codes of at most 12 bits under bit-flip errors, where
every one of the 2**n error patterns can be enumerated. That is what makes the
oracle an independently known solution rather than a second opinion. These are
classical textbook codes used as software-correctness fixtures; they are not
surface-code decoders and say nothing about any hardware decoder's accuracy.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from itertools import product

from qfabric.gari_reference import (
    MAX_EXHAUSTIVE_BITS,
    Matrix,
    _matrix,
    _parity_syndrome,
)

Bits = tuple[int, ...]


@dataclass(frozen=True, slots=True)
class DecodingProblem:
    """Parity checks H and the logical observables L that define a failure."""

    name: str
    checks: Matrix
    logicals: Matrix

    def __post_init__(self) -> None:
        checks, logicals = _matrix(self.checks, "checks"), _matrix(self.logicals, "logicals")
        if len(checks[0]) != len(logicals[0]) or len(checks[0]) > MAX_EXHAUSTIVE_BITS:
            raise ValueError("checks and logicals need the same width of at most 12 bits")
        object.__setattr__(self, "checks", checks)
        object.__setattr__(self, "logicals", logicals)

    @property
    def bits(self) -> int:
        return len(self.checks[0])

    def syndrome(self, error: Bits) -> Bits:
        return _parity_syndrome(self.checks, error)

    def logical_class(self, error: Bits) -> Bits:
        return _parity_syndrome(self.logicals, error)


def repetition_code(distance: int) -> DecodingProblem:
    """Bit-flip repetition code: adjacent-pair parity checks, one logical bit."""
    if type(distance) is not int or not 3 <= distance <= MAX_EXHAUSTIVE_BITS - 1 or not distance % 2:
        raise ValueError("repetition distance must be an odd integer in 3..11")
    checks = tuple(
        tuple(int(column in (row, row + 1)) for column in range(distance))
        for row in range(distance - 1)
    )
    # A residual error is a codeword (all zeros or all ones); bit 0 tells which.
    return DecodingProblem(f"repetition_{distance}", checks, ((1,) + (0,) * (distance - 1),))


def hamming_7_4() -> DecodingProblem:
    """[7,4,3] Hamming code; column j of H is the binary expansion of j+1."""
    checks = tuple(
        tuple((column + 1) >> shift & 1 for column in range(7)) for shift in (2, 1, 0)
    )
    # A nonzero codeword always has a nonzero data bit (positions 3, 5, 6, 7).
    logicals = tuple(tuple(int(column == data) for column in range(7)) for data in (2, 4, 5, 6))
    return DecodingProblem("hamming_7_4", checks, logicals)


def _binary(vector: object, width: int, name: str) -> Bits:
    if (
        not isinstance(vector, tuple) or len(vector) != width
        or any(type(bit) is not int or bit not in (0, 1) for bit in vector)
    ):
        raise ValueError(f"{name} must be a tuple of {width} binary integers")
    return vector


@cache
def coset_table(problem: DecodingProblem) -> dict[Bits, tuple[int, frozenset[Bits]]]:
    """Oracle: syndrome -> (minimum error weight, logical classes reaching it).

    Built by enumerating all 2**n errors, with no decoding algorithm involved.
    More than one logical class at the minimum weight means minimum-weight
    decoding is genuinely ambiguous for that syndrome.
    """
    table: dict[Bits, tuple[int, set[Bits]]] = {}
    for error in product((0, 1), repeat=problem.bits):
        weight, key = sum(error), problem.syndrome(error)
        known = table.get(key)
        if known is None or weight < known[0]:
            table[key] = (weight, {problem.logical_class(error)})
        elif weight == known[0]:
            known[1].add(problem.logical_class(error))
    return {key: (weight, frozenset(classes)) for key, (weight, classes) in table.items()}


def majority_vote(problem: DecodingProblem, syndrome: Bits) -> Bits:
    """Repetition code: rebuild the error up to complement, keep the lighter one."""
    syndrome = _binary(syndrome, problem.bits - 1, "syndrome")
    error = [0]
    for bit in syndrome:
        error.append(error[-1] ^ bit)
    if 2 * sum(error) > problem.bits:
        error = [bit ^ 1 for bit in error]
    return tuple(error)


def prefix_without_vote(problem: DecodingProblem, syndrome: Bits) -> Bits:
    """NEGATIVE CONTROL, deliberately wrong: skips the majority step.

    It always reproduces the syndrome, so only a logical-class check exposes it.
    A benchmark that reports this decoder as correct is itself broken.
    """
    syndrome = _binary(syndrome, problem.bits - 1, "syndrome")
    error = [0]
    for bit in syndrome:
        error.append(error[-1] ^ bit)
    return tuple(error)


def hamming_syndrome(problem: DecodingProblem, syndrome: Bits) -> Bits:
    """Hamming code: the syndrome read as a binary number is the flipped position."""
    position = int("".join(map(str, _binary(syndrome, 3, "syndrome"))), 2)
    return tuple(int(column + 1 == position) for column in range(7))


Decoder = Callable[[DecodingProblem, Bits], Bits]
# Which code family each registered decoder is defined for.
DECODERS: dict[str, tuple[str, Decoder]] = {
    "majority_vote": ("repetition", majority_vote),
    "negative_control_prefix": ("repetition", prefix_without_vote),
    "hamming_syndrome": ("hamming_7_4", hamming_syndrome),
}


def judge_correction(problem: DecodingProblem, syndrome: Bits, correction: object) -> str:
    """Classify one decoder output: agree, disagree, ambiguous or invalid."""
    try:
        correction = _binary(correction, problem.bits, "correction")
    except ValueError:
        return "invalid"
    if problem.syndrome(correction) != syndrome:
        return "invalid"  # does not even explain the observed syndrome
    _, classes = coset_table(problem)[syndrome]
    if len(classes) > 1:
        return "ambiguous"
    return "agree" if problem.logical_class(correction) in classes else "disagree"


def failing_weight_counts(problem: DecodingProblem, decoder: Decoder) -> tuple[int, ...]:
    """Entry w counts the weight-w errors after which ``decoder`` leaves a logical flip.

    Found by enumerating all 2**n errors, so it involves no sampling and no
    floating point. It fixes the decoder's failure probability for every p.
    """
    corrections: dict[Bits, Bits] = {}
    counts = [0] * (problem.bits + 1)
    for error in product((0, 1), repeat=problem.bits):
        key = problem.syndrome(error)
        if key not in corrections:
            corrections[key] = decoder(problem, key)
        residual = tuple(a ^ b for a, b in zip(error, corrections[key], strict=True))
        counts[sum(error)] += any(problem.logical_class(residual))
    return tuple(counts)


def failure_probability(counts: tuple[int, ...], p: float) -> float:
    """Sum of count[w] * p**w * (1-p)**(n-w) for i.i.d. bit flips with probability p.

    Evaluated in exact rational arithmetic and rounded once, so the result does
    not depend on summation order, Python version or the platform's pow().
    """
    bits, flip = len(counts) - 1, Fraction(p)
    return float(sum(
        count * flip ** weight * (1 - flip) ** (bits - weight)
        for weight, count in enumerate(counts)
    ))
