"""Soft-decision row selection for the GF(2) rank tools (PLAN M5).

Hard-decision rank sees a single flipped bit as full rank. Rows made only of reliable bits are
much more likely to be error-free, so the soft variant orders the candidate rows by reliability
and keeps the best ones; the elimination itself stays the shared kernel's.

LLR convention as everywhere in `dsp`: a positive LLR means bit 0.
"""

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import ArrayLike, NDArray

from dsp.gf2.windows import Bits, check_rows, rows_available


def hard_bits(llr: ArrayLike) -> Bits:
    """Hard decisions from LLRs (positive means 0)."""
    return (np.asarray(llr, dtype=np.float64) < 0).astype(np.uint8)


def reliable_window_matrix(
    llr: ArrayLike, width: int, *, stride: int = 1, offset: int = 0, keep: int
) -> Bits:
    """The `keep` most reliable `width`-bit windows, hard-decided, most reliable first.

    A window's reliability is its weakest bit, min |LLR|; ties keep stream order. `keep` must
    satisfy the row-count rule (at least width + 30), and the stream must hold that many windows.
    """
    check_rows(width, keep)
    x = np.asarray(llr, dtype=np.float64)
    available = rows_available(len(x), width, stride, offset)
    if keep > available:
        raise ValueError(f"asked for {keep} windows but the stream holds {available}")
    windows = sliding_window_view(x[offset:], width)[::stride]
    # The weakest bit of every window as a running minimum of shifted copies of |x| (the same
    # values as the minimum over each window's row, without building the |windows| matrix).
    magnitude = np.abs(x[offset:])
    count = len(magnitude) - width + 1
    running = magnitude[:count].copy()
    for shift in range(1, width):
        np.minimum(running, magnitude[shift : shift + count], out=running)
    weakest: NDArray[np.float64] = running[::stride]
    order = np.argsort(-weakest, kind="stable")[:keep]
    return np.ascontiguousarray((windows[order] < 0).astype(np.uint8))
