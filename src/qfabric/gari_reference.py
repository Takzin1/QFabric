"""Independent reference for the *linear algebra* of GARI, NOT a GARI decoder.

Maan et al., Nature Communications 17, 3965 (2026), DOI:
10.1038/s41467-026-70556-3, equations (1)--(6), page 3.
This implementation is original, standard-library-only, and intentionally
bounded to tiny synthetic binary matrices for exhaustive equivalence checks.
It does not implement normalized min-sum, ensemble decoding or FPGA timing.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product

Matrix = tuple[tuple[int, ...], ...]
MAX_SMALL_COLUMNS = 16
MAX_SMALL_ROWS = 24
MAX_EXHAUSTIVE_BITS = 12


def _matrix(rows: object, name: str) -> Matrix:
    if not isinstance(rows, (list, tuple)) or not 1 <= len(rows) <= MAX_SMALL_ROWS:
        raise ValueError(f"{name}: expected 1..24 binary rows")
    if not all(isinstance(row, (list, tuple)) for row in rows):
        raise TypeError(f"{name}: each row must be a sequence")
    width = len(rows[0])
    if not 1 <= width <= MAX_SMALL_COLUMNS or any(len(row) != width for row in rows):
        raise ValueError(f"{name}: rectangular matrix must have 1..16 columns")
    if any(type(x) is not int or x not in (0, 1) for row in rows for x in row):
        raise ValueError(f"{name}: entries must be binary integers, not booleans")
    return tuple(tuple(row) for row in rows)


def _columns(a: Matrix) -> tuple[tuple[int, ...], ...]:
    return tuple(zip(*a, strict=True))


def _parity_syndrome(a: Matrix, bits: tuple[int, ...]) -> tuple[int, ...]:
    if not a or len(bits) != len(a[0]):
        raise ValueError("syndrome vector width mismatch")
    return tuple(sum(bit * coefficient for coefficient, bit in zip(row, bits, strict=True)) % 2 for row in a)


def four_cycles(a: Matrix) -> int:
    """Number of distinct 4-cycles (two rows and two shared error columns)."""
    if not a:
        return 0
    return sum(
        n * (n - 1) // 2
        for upper, lower in combinations(a, 2)
        if (n := sum(x & y for x, y in zip(upper, lower, strict=True))) >= 2
    )


@dataclass(frozen=True, slots=True)
class GariReference:
    original: Matrix
    augmented: Matrix
    dx: Matrix
    dz: Matrix
    ux_index: tuple[int, ...]  # Y-column -> unique DX-column matching its X syndrome
    vz_index: tuple[int, ...]  # Y-column -> unique DZ-column matching its Z syndrome
    y_count: int

    @property
    def z_count(self) -> int:
        return len(self.dx[0])

    @property
    def x_count(self) -> int:
        return len(self.dz[0])

    @property
    def original_width(self) -> int:
        return self.z_count + self.x_count + self.y_count

    def lift(self, original_errors: tuple[int, ...]) -> tuple[int, ...]:
        """Equation (3), eZ_tilde=eZ+UeY; eX_tilde=eX+VeY in GF(2)."""
        if len(original_errors) != self.original_width or any(type(x) is not int or x not in (0, 1) for x in original_errors):
            raise ValueError("original error vector must be binary and match original width")
        nz, nx = self.z_count, self.x_count
        ez = original_errors[:nz]
        ex = original_errors[nz:nz + nx]
        ey = original_errors[nz + nx:]
        tz = tuple(ez[i] ^ (sum(ey[j] for j, k in enumerate(self.ux_index) if k == i) % 2) for i in range(nz))
        tx = tuple(ex[i] ^ (sum(ey[j] for j, k in enumerate(self.vz_index) if k == i) % 2) for i in range(nx))
        return original_errors + tz + tx

    def assert_equivalent(self) -> int:
        """Exhaustively verify original and lifted augmented syndrome constraints."""
        if self.original_width > MAX_EXHAUSTIVE_BITS:
            raise ValueError("exhaustive check limited to 12 original error bits")
        mx = len(self.dx)
        count = 0
        for bits in product((0, 1), repeat=self.original_width):
            original_errors = tuple(bits)
            upper = _parity_syndrome(self.original, original_errors)
            lifted = _parity_syndrome(self.augmented, self.lift(original_errors))
            if lifted != upper[:mx] + upper[mx:] + (0,) * (self.z_count + self.x_count):
                raise AssertionError("GARI lifting does not preserve syndrome")
            count += 1
        return count


def build_gari_reference(dx: object, dz: object, y_x: object, y_z: object) -> GariReference:
    """Reference Eq. (5): DX, DZ, and Y submatrices of the correlated DEM.

    DX and DZ columns must each be unique, and every Y column must match
    one column in *each*. These are paper assumptions, not arbitrary DEM rules.
    """
    dxm, dzm = _matrix(dx, "DX"), _matrix(dz, "DZ")
    yxm, yzm = _matrix(y_x, "DX-prime"), _matrix(y_z, "DZ-prime")
    if len(yxm) != len(dxm) or len(yzm) != len(dzm):
        raise ValueError("Y detector rows must match X/Z detector dimensions")
    ny = len(yxm[0])
    if len(yzm[0]) != ny:
        raise ValueError("Y error columns must align in both detector types")
    dxcols, dzcols = _columns(dxm), _columns(dzm)
    if len(set(dxcols)) != len(dxcols) or len(set(dzcols)) != len(dzcols):
        raise ValueError("merged single-type error columns must be unique")
    try:
        uidx = tuple(dxcols.index(col) for col in _columns(yxm))
        vidx = tuple(dzcols.index(col) for col in _columns(yzm))
    except ValueError as exc:
        raise ValueError("Y error column must match a unique DX and DZ column") from exc
    nz, nx = len(dxcols), len(dzcols)
    zeros_z, zeros_x, zeros_y = (0,) * nz, (0,) * nx, (0,) * ny
    original = (
        tuple(row + zeros_x + yy for row, yy in zip(dxm, yxm, strict=True))
        + tuple(zeros_z + row + yy for row, yy in zip(dzm, yzm, strict=True))
    )
    # Eq (5): [0 0 0 DX 0]; [0 0 0 0 DZ];
    #         [I 0 U I 0]; [0 I V 0 I].
    augmented = (
        tuple(zeros_z + zeros_x + zeros_y + row + zeros_x for row in dxm)
        + tuple(zeros_z + zeros_x + zeros_y + zeros_z + row for row in dzm)
    )
    for i in range(nz):
        iz = tuple(int(j == i) for j in range(nz))
        urow = tuple(int(k == i) for k in uidx)
        augmented += (iz + zeros_x + urow + iz + zeros_x,)
    for i in range(nx):
        ix = tuple(int(j == i) for j in range(nx))
        vrow = tuple(int(k == i) for k in vidx)
        augmented += (zeros_z + ix + vrow + zeros_z + ix,)
    return GariReference(original, augmented, dxm, dzm, uidx, vidx, ny)


def per_round_logical_error_rate(failures: int, samples: int, rounds: int) -> float:
    """Equation (7), without pretending that per-round trials are independent.

    Rates >1/2 are outside the real-valued model in the cited transform.
    Use expm1/log1p for numerical stability when failures/samples is tiny.
    """
    import math

    if any(type(v) is not int for v in (failures, samples, rounds)):
        raise TypeError("failure/sample/round counts must be integer (not bool)")
    if samples <= 0 or rounds <= 0 or not 0 <= failures <= samples // 2:
        raise ValueError("require 0 <= failures/samples <= 1/2 and positive counts")
    if failures == 0:
        return 0.0
    p = failures / samples
    return -0.5 * math.expm1(math.log1p(-2 * p) / rounds) if p < 0.5 else 0.5


def bpt_efficiency(n: int, k: int, distance: int) -> float:
    """Figure 1/5 x axis = k*d^2/n; not a decoding accuracy estimator."""
    if any(type(v) is not int for v in (n, k, distance)):
        raise TypeError("code sizes must be integers")
    if n <= 0 or not 0 < k <= n or not 0 < distance <= n:
        raise ValueError("invalid code parameters")
    return k * distance * distance / n
