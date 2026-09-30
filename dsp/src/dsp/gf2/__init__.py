"""The shared GF(2) kernel (PLAN M5): bit-packed matrices, elimination, rank scans.

Blind FEC and interleaver identification all go through here; there is no second elimination
routine elsewhere in Sanket.
"""

from dsp.gf2.eliminate import nullspace, rank, rref
from dsp.gf2.matrix import pack, parity_counts, row_weights, unpack
from dsp.gf2.soft import hard_bits, reliable_window_matrix
from dsp.gf2.windows import (
    MIN_EXTRA_ROWS,
    RankPoint,
    check_rows,
    first_deficient_width,
    rank_profile,
    rows_available,
    window_matrix,
)

__all__ = [
    "MIN_EXTRA_ROWS",
    "RankPoint",
    "check_rows",
    "first_deficient_width",
    "hard_bits",
    "nullspace",
    "pack",
    "parity_counts",
    "rank",
    "rank_profile",
    "reliable_window_matrix",
    "row_weights",
    "rows_available",
    "rref",
    "unpack",
    "window_matrix",
]
