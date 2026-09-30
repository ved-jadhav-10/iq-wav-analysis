"""Bit-packed GF(2) matrices (PLAN M5, the shared kernel).

A matrix of `rows x cols` bits is stored as `rows x ceil(cols / 64)` uint64 words. Column `j` is
bit `j % 64` (least significant first) of word `j // 64`, so `pack` and `unpack` are inverses and
nothing else in Sanket needs to know the layout. Padding bits above `cols` are always zero.
"""

import numba  # pyright: ignore[reportMissingTypeStubs]
import numpy as np
from numpy.typing import ArrayLike, NDArray

Bits = NDArray[np.uint8]
Words = NDArray[np.uint64]


def words_for(cols: int) -> int:
    return -(-cols // 64)


def pack(bits: ArrayLike) -> Words:
    """Pack a 2-D array of 0/1 values into rows of uint64 words."""
    a = np.asarray(bits)
    if a.ndim != 2:
        raise ValueError("pack takes a 2-D array of bits")
    if a.size and (a.min() < 0 or a.max() > 1):
        raise ValueError("bits must be 0 or 1")
    rows, cols = a.shape
    padded = np.zeros((rows, words_for(cols) * 8), np.uint8)
    packed = np.packbits(a.astype(np.uint8), axis=1, bitorder="little")
    padded[:, : packed.shape[1]] = packed
    return np.ascontiguousarray(padded).view("<u8").astype(np.uint64)


def unpack(words: Words, cols: int) -> Bits:
    """The inverse of `pack`: back to a rows x cols array of 0/1 bytes."""
    rows = words.shape[0]
    raw = np.ascontiguousarray(words.astype("<u8")).view(np.uint8).reshape(rows, words.shape[1] * 8)
    return np.unpackbits(raw, axis=1, bitorder="little")[:, :cols]


@numba.njit(cache=True, inline="always")  # pyright: ignore[reportUntypedFunctionDecorator]
def popcount(x: np.uint64) -> np.uint64:  # pragma: no cover - compiled
    """Number of set bits in a 64-bit word (SWAR; no dependency on a NumPy or CPU intrinsic)."""
    x = x - ((x >> np.uint64(1)) & np.uint64(0x5555555555555555))
    x = (x & np.uint64(0x3333333333333333)) + ((x >> np.uint64(2)) & np.uint64(0x3333333333333333))
    x = (x + (x >> np.uint64(4))) & np.uint64(0x0F0F0F0F0F0F0F0F)
    return (x * np.uint64(0x0101010101010101)) >> np.uint64(56)


@numba.njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _row_weights(m: Words) -> NDArray[np.int64]:  # pragma: no cover - compiled
    out = np.zeros(m.shape[0], np.int64)
    for i in range(m.shape[0]):
        total = np.uint64(0)
        for w in range(m.shape[1]):
            total += popcount(m[i, w])
        out[i] = np.int64(total)
    return out


def row_weights(m: Words) -> NDArray[np.int64]:
    """Hamming weight of every row."""
    return _row_weights(m)


@numba.njit(cache=True)  # pyright: ignore[reportUntypedFunctionDecorator]
def _parity_counts(m: Words, vectors: Words) -> NDArray[np.int64]:  # pragma: no cover - compiled
    out = np.zeros(vectors.shape[0], np.int64)
    for v in range(vectors.shape[0]):
        count = 0
        for i in range(m.shape[0]):
            total = np.uint64(0)
            for w in range(m.shape[1]):
                total += popcount(m[i, w] & vectors[v, w])
            if total & np.uint64(1):
                count += 1
        out[v] = count
    return out


def parity_counts(m: Words, vectors: Words) -> NDArray[np.int64]:
    """For each vector v, how many rows r of `m` have r . v = 1 (the syndrome weight of v).

    Both are packed with the same column count. A vector orthogonal to every row of a clean
    codeword matrix scores 0; on rows that are not codewords it scores about half of them.
    """
    if m.shape[1] != vectors.shape[1]:
        raise ValueError("matrix and vectors must have the same number of columns")
    return _parity_counts(m, vectors)
