"""Gauss-Jordan elimination over GF(2) on packed matrices (PLAN M5).

This is the only elimination routine in Sanket: code length, sync offset, puncturing and
interleaver period all reduce to a rank or a null space computed here. Everything is exact
integer arithmetic; noise handling (which rows to feed in) is the caller's job, see `soft`.
"""

import numba  # pyright: ignore[reportMissingTypeStubs]
import numpy as np
from numpy.typing import NDArray

from dsp.gf2.matrix import Words, pack, unpack, words_for


@numba.njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _rref(m: Words, cols: int) -> NDArray[np.int64]:  # pragma: no cover - compiled
    """Reduce `m` in place to reduced row echelon form; return the pivot column of each
    non-zero row, in row order."""
    rows = m.shape[0]
    words = m.shape[1]
    pivots = np.empty(min(rows, cols), np.int64)
    r = 0
    for c in range(cols):
        if r == rows:
            break
        w = c >> 6
        bit = np.uint64(1) << np.uint64(c & 63)
        p = -1
        for i in range(r, rows):
            if m[i, w] & bit:
                p = i
                break
        if p < 0:
            continue
        if p != r:
            for k in range(words):
                tmp = m[r, k]
                m[r, k] = m[p, k]
                m[p, k] = tmp
        for i in range(rows):
            if i != r and (m[i, w] & bit):
                for k in range(words):
                    m[i, k] ^= m[r, k]
        pivots[r] = c
        r += 1
    return pivots[:r].copy()


def rref(m: Words, cols: int) -> tuple[Words, NDArray[np.int64]]:
    """Reduced row echelon form of a packed matrix and its pivot columns.

    Returns a new matrix (`m` is not modified) with the zero rows moved to the bottom.
    """
    _check(m, cols)
    reduced = m.copy()
    return reduced, _rref(reduced, cols)


def rank(m: Words, cols: int) -> int:
    """Rank of a packed matrix over GF(2)."""
    return len(rref(m, cols)[1])


def nullspace(m: Words, cols: int) -> Words:
    """A basis of {x : m x = 0} as packed rows (one vector per row, `cols` bits each).

    These are the dual vectors of the row space: a parity check of the code whose codewords
    are the rows of `m`. There are `cols - rank` of them.
    """
    reduced, pivots = rref(m, cols)
    is_pivot = np.zeros(cols, bool)
    is_pivot[pivots] = True
    free = np.flatnonzero(~is_pivot)
    basis = np.zeros((len(free), cols), np.uint8)
    dense = unpack(reduced[: len(pivots)], cols)
    for k, f in enumerate(free):
        basis[k, f] = 1
        # Row i of the reduced matrix reads x[pivot_i] + sum(free entries) = 0.
        basis[k, pivots] = dense[:, f]
    return pack(basis)


def _check(m: Words, cols: int) -> None:
    if m.dtype != np.uint64 or m.ndim != 2:
        raise ValueError("a packed matrix is a 2-D uint64 array")
    if m.shape[1] != words_for(cols):
        raise ValueError(f"{cols} columns need {words_for(cols)} words per row, got {m.shape[1]}")
