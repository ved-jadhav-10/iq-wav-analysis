"""Bit-stream windows as GF(2) matrices, and the rank scan built on them (PLAN M5).

A linear code with parity constraints makes the matrix whose rows are windows of the coded
stream rank-deficient once the window is wide enough to contain a whole constraint, *if* the
rows are aligned to the code's frame. A stream with no structure stays full rank. The scan is
a hard-decision test: it needs rows that are (nearly) error-free, which is what `soft` selects.

The row-count rule is enforced here, not left to callers: a `width`-column matrix needs at least
`width + MIN_EXTRA_ROWS` rows, so a random full-rank matrix is not mistaken for a deficient one
(the chance a random `w + 30` by `w` matrix is rank-deficient is below 2**-29).
"""

from dataclasses import dataclass

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import ArrayLike, NDArray

from dsp.gf2.eliminate import rank
from dsp.gf2.matrix import pack

Bits = NDArray[np.uint8]

MIN_EXTRA_ROWS = 30


def rows_available(n_bits: int, width: int, stride: int = 1, offset: int = 0) -> int:
    """How many `width`-bit windows, `stride` apart from bit `offset`, fit in `n_bits`."""
    if width < 1 or stride < 1 or offset < 0:
        raise ValueError("width and stride must be positive and offset non-negative")
    return max(0, (n_bits - offset - width) // stride + 1)


def check_rows(width: int, rows: int) -> None:
    """Refuse a matrix with too few rows for its width (L >= w + 30)."""
    if rows < width + MIN_EXTRA_ROWS:
        raise ValueError(
            f"a {width}-column GF(2) matrix needs at least {width + MIN_EXTRA_ROWS} rows "
            f"(width + {MIN_EXTRA_ROWS}) to tell a rank drop from chance, got {rows}"
        )


def window_matrix(
    bits: ArrayLike, width: int, *, stride: int = 1, offset: int = 0, rows: int | None = None
) -> Bits:
    """Rows are `width`-bit windows of `bits`, starting at `offset` and `stride` bits apart.

    With `stride` equal to the code's output block length and `offset` on a block boundary, the
    rows are aligned to the code's frame. Uses all available windows unless `rows` caps them.
    """
    b = np.asarray(bits, dtype=np.uint8)
    available = rows_available(len(b), width, stride, offset)
    count = available if rows is None else min(rows, available)
    check_rows(width, count)
    view = sliding_window_view(b[offset:], width)[::stride]
    return np.ascontiguousarray(view[:count])


@dataclass(frozen=True)
class RankPoint:
    width: int
    rows: int
    rank: int

    @property
    def deficiency(self) -> int:
        """Columns the rows do not span: 0 for a full-rank (structureless) matrix."""
        return self.width - self.rank


def rank_profile(
    bits: ArrayLike, widths: range | list[int], *, stride: int = 1, offset: int = 0
) -> tuple[RankPoint, ...]:
    """Rank of the window matrix at each width. Each uses `width + 2 * MIN_EXTRA_ROWS` rows
    (fewer if the stream is short, but never below the row-count rule, which raises)."""
    b = np.asarray(bits, dtype=np.uint8)
    points: list[RankPoint] = []
    for width in widths:
        m = window_matrix(b, width, stride=stride, offset=offset, rows=width + 2 * MIN_EXTRA_ROWS)
        points.append(RankPoint(width, len(m), rank(pack(m), width)))
    return tuple(points)


def first_deficient_width(profile: tuple[RankPoint, ...]) -> int | None:
    """The narrowest scanned width whose matrix is rank-deficient, or None if none is."""
    return next((p.width for p in profile if p.deficiency > 0), None)
