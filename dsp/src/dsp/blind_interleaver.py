"""A block interleaver found blind, in front of the K=7 rate-1/2 code (PLAN M5).

A block interleaver of R rows and C columns writes the code stream by rows and reads it by
columns, so in the received stream the R-th bit after any bit is the next bit of the code stream:
every R-th received bit is a contiguous stretch of code bits (one row) for C bits, and then the
next block's row. The code's parity syndrome (`dsp.fec.viterbi`) is near 0 on such a stretch and
stays at 0.5 on any other stride, so scanning strides 2 ... `MAX_STRIDE` finds R with no
catalogue. Where the stretches end, every C bits, the parity checks that span the join fail: the
syndrome bits folded modulo a trial row length show a band of failures only at the true C (or a
multiple of it), which gives C. The result is a few `Block(R, C)` candidates whose alignment is
then found, and which are decided, exactly as for the catalogue (`dsp.analyse`).

Limits, all stated in the result rather than hidden: only the block interleaver (a helical one's
stride breaks every R bits, too short for the K=7 checks); only hard decisions; only the K=7
code's syndrome; R up to `MAX_STRIDE`, blocks up to `MAX_BLOCK` bits. A stream with structure at
many strides (idle, repeated) is refused rather than read.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dsp.deinterleave import Block
from dsp.fec.viterbi import syndrome_bits

MAX_STRIDE = 256
MAX_BITS = 1 << 20  # of the stream read
ROW_CAP = 16384  # bits of one strided row used
MIN_ROW_BITS = 768  # a row shorter than this has too few windows to test
Z_STRIDE = 7.0  # below the mean of uniform windows: 7 sigma, over 2 phases x MAX_STRIDE strides
MAX_STRIDES = 3  # more significant strides than this: the stream is structured, not interleaved
MIN_ROW_LENGTH = 8
MAX_ROW_LENGTH = 4096
MAX_BLOCK = 65536  # R x C
Z_FOLD = 6.0  # the folded syndrome's contrast must beat a chi-square null by this many sigma
# The hypotheses a stream can add to a grid: strides kept x row-length candidates x block size
# (every alignment of every candidate block is a cell).
CANDIDATES_PER_STRIDE = 2
MAX_CANDIDATE_CELLS = MAX_STRIDES * CANDIDATES_PER_STRIDE * MAX_BLOCK


@dataclass(frozen=True)
class Stride:
    """A stride at which the parity syndrome of every `stride`-th bit is far below chance."""

    stride: int
    phase: int  # 0 or 1: which bit of the strided row pairs first
    rate: float  # mean syndrome, 0.5 for unrelated bits
    z: float  # standard deviations below 0.5
    windows: int


@dataclass(frozen=True)
class BlindBlock:
    """One block-interleaver candidate: `Block(rows, cols)` and the evidence behind it."""

    block: Block
    stride: Stride
    fold_z: float  # how strongly the syndrome failures fold at this row length

    @property
    def evidence(self) -> str:
        s = self.stride
        return (
            f"Every {s.stride}th received bit is a stretch of the K=7 code: syndrome "
            f"{s.rate:.3f} over {s.windows:,} windows ({s.z:.1f} sigma below chance, "
            f"{2 * MAX_STRIDE - 2} strides and phases tried); its checks fail at joins every "
            f"{self.block.cols} bits (folded contrast {self.fold_z:.1f} sigma)"
        )


def _row(hard: NDArray[np.uint8], stride: int, phase: int) -> NDArray[np.uint8]:
    row = hard[::stride][:ROW_CAP][phase:]
    return row[: len(row) // 2 * 2]


def scan_strides(hard: NDArray[np.uint8]) -> tuple[Stride, ...]:
    """Strides whose rows satisfy the code's parity checks, best first. Empty for a stream with
    no such stride, or (structured, not interleaved) more than `MAX_STRIDES` of them."""
    hard = np.asarray(hard, np.uint8)[:MAX_BITS]
    found: list[Stride] = []
    for stride in range(2, MAX_STRIDE + 1):
        rows = [_row(hard, stride, phase) for phase in (0, 1)]
        if len(rows[0]) < MIN_ROW_BITS:
            break  # later strides only have shorter rows
        for phase, row in enumerate(rows):
            w = syndrome_bits(row[None, :])[0]
            if len(w) == 0:
                continue
            rate = float(w.mean())
            z = (0.5 - rate) * 2.0 * np.sqrt(len(w))
            if z >= Z_STRIDE:
                found.append(Stride(stride, phase, rate, float(z), len(w)))
    # One stride can pass at both phases (an even row length pairs the same way from either
    # start only by chance): keep the better one.
    best: dict[int, Stride] = {}
    for s in found:
        if s.stride not in best or s.rate < best[s.stride].rate:
            best[s.stride] = s
    if not best or len(best) > MAX_STRIDES:
        return ()
    return tuple(sorted(best.values(), key=lambda s: s.rate))


def fold_contrast(w: NDArray[Any], length: int) -> float:
    """How far the syndrome failures `w` (one per code step, so two bits apart) differ between
    positions modulo `length` bits, in standard deviations of a chi-square null."""
    mean = float(w.mean())
    if mean <= 0.0 or mean >= 1.0:
        return 0.0
    position = (np.arange(len(w)) * 2) % length
    count = np.bincount(position, minlength=length).astype(np.float64)
    total = np.bincount(position, weights=w, minlength=length)
    used = count > 0
    dof = int(used.sum()) - 1
    if dof < 4:
        return 0.0
    p = total[used] / count[used]
    stat = float((count[used] * (p - mean) ** 2).sum() / (mean * (1.0 - mean)))
    return (stat - dof) / float(np.sqrt(2.0 * dof))


def row_lengths(hard: NDArray[np.uint8], stride: Stride) -> tuple[tuple[int, float], ...]:
    """Candidate row lengths C (and the contrast behind each) for a stride: the length where
    the syndrome failures fold most sharply, and its double, since a half-length folds as well
    when the joins are two bits apart. Empty when nothing folds."""
    row = _row(np.asarray(hard, np.uint8)[:MAX_BITS], stride.stride, stride.phase)
    w = syndrome_bits(row[None, :])[0].astype(np.float64)
    top = min(MAX_ROW_LENGTH, len(row) // 4)
    if top <= MIN_ROW_LENGTH:
        return ()
    scores = [(fold_contrast(w, c), c) for c in range(MIN_ROW_LENGTH, top + 1)]
    z, c = max(scores, key=lambda t: (round(t[0], 6), -t[1]))
    if z < Z_FOLD:
        return ()
    by_length = {length: score for score, length in scores}
    out = [(c, z)]
    if 2 * c <= MAX_ROW_LENGTH and 2 * c in by_length:
        out.append((2 * c, by_length[2 * c]))
    return tuple(out)


def find_blocks(hard: NDArray[np.uint8]) -> tuple[BlindBlock, ...]:
    """Block interleavers the stream's own structure names, best first, at most
    `MAX_STRIDES * CANDIDATES_PER_STRIDE` of them."""
    hard = np.asarray(hard, np.uint8)
    out: list[BlindBlock] = []
    for stride in scan_strides(hard):
        for cols, z in row_lengths(hard, stride):
            if stride.stride * cols <= MAX_BLOCK:
                out.append(BlindBlock(Block(stride.stride, cols), stride, z))
    return tuple(out)
