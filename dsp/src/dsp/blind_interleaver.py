"""A block or helical interleaver found blind, in front of the K=7 rate-1/2 code (PLAN M5).

A block interleaver of R rows and C columns writes the code stream by rows and reads it by
columns, so in the received stream the R-th bit after any bit is the next bit of the code stream:
every R-th received bit is a contiguous stretch of code bits (one row) for C bits, and then the
next block's row. The code's parity syndrome (`dsp.fec.viterbi`) is near 0 on such a stretch and
stays at 0.5 on any other stride, so scanning strides 2 ... `MAX_STRIDE` finds R with no
catalogue. Where the stretches end, every C bits, the parity checks that span the join fail: the
syndrome bits folded modulo a trial row length show a band of failures only at the true C (or a
multiple of it), which gives C. The result is a few `Block(R, C)` candidates whose alignment is
then found, and which are decided, exactly as for the catalogue (`dsp.analyse`).

A helical (diagonal) interleaver of R rows reads column c starting c rows down, so the code
stream advances by R - 1 received bits, or by 2R - 1 where its column wraps: a walk with a fixed
rule once the column phase (the block start modulo R) is known. `find_helical` tries every walk
for R up to `HELIX_BRUTE` at every column phase, and for larger R only the strides R - 1 that the
constant-stride scan ranks best (a constant stride reads runs of R code bits between the wraps,
enough for the K=7 checks from R of about 20), judges each walk by the same parity syndrome, and
finds the row length by folding the failures where the walk crosses into the next block.

Limits, all stated in the result rather than hidden: only block and helical interleavers; only
hard decisions; only the K=7 code's syndrome; R up to `MAX_STRIDE`, blocks up to `MAX_BLOCK` bits;
a helical R above `HELIX_BRUTE` needs the constant-stride prefilter to rank its stride among the
best three. A stream with structure at many strides (idle, repeated) is refused rather than read.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dsp.deinterleave import Block, Helical
from dsp.fec.viterbi import syndrome_bits

MAX_STRIDE = 256
Float = NDArray[np.float64]
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
HELIX_BRUTE = 32  # rows tried exhaustively, at every column phase
HELIX_PREFILTER = 3  # larger row counts: the best-ranked strides R - 1 only
HELIX_WALK = 96  # code bits per walk when judging a (rows, column phase)
Z_HELIX = 7.0  # standard deviations below chance, over about 1,300 hypotheses
MAX_HELIX_RATE = 0.4  # a walk through the right helix reads the code at its raw error rate
HELIX_MARGIN = 0.05  # the walk's rate must beat the constant stride R - 1's by this much
BALANCE = (0.35, 0.65)  # share of ones in a walk's bits: a constant or idle row is not code


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
    """One interleaver candidate, `Block(rows, cols)` or `Helical(rows, cols)`, and the evidence
    behind it."""

    block: Block | Helical
    stride: Stride
    fold_z: float  # how strongly the syndrome failures fold at this row length
    column_phase: int | None = None  # helical: the block start modulo the rows

    @property
    def evidence(self) -> str:
        s = self.stride
        if isinstance(self.block, Helical):
            return (
                f"A helical walk of {s.stride} rows (step {s.stride - 1} received bits, "
                f"{2 * s.stride - 1} where the column wraps, column phase {self.column_phase}) "
                f"reads a stretch of the K=7 code: syndrome {s.rate:.3f} over {s.windows:,} "
                f"windows ({s.z:.1f} sigma below chance, {HELIX_HYPOTHESES} walks tried); its "
                f"checks fail at joins every {self.block.cols} bits (folded contrast "
                f"{self.fold_z:.1f} sigma)"
            )
        return (
            f"Every {s.stride}th received bit is a stretch of the K=7 code: syndrome "
            f"{s.rate:.3f} over {s.windows:,} windows ({s.z:.1f} sigma below chance, "
            f"{2 * MAX_STRIDE - 2} strides and phases tried); its checks fail at joins every "
            f"{self.block.cols} bits (folded contrast {self.fold_z:.1f} sigma)"
        )


def _row(hard: NDArray[np.uint8], stride: int, phase: int) -> NDArray[np.uint8]:
    row = hard[::stride][:ROW_CAP][phase:]
    return row[: len(row) // 2 * 2]


def _stride_scan(hard: NDArray[np.uint8]) -> list[Stride]:
    """The best phase of every stride 2 ... MAX_STRIDE whose row is long enough to test."""
    hard = np.asarray(hard, np.uint8)[:MAX_BITS]
    out: list[Stride] = []
    for stride in range(2, MAX_STRIDE + 1):
        rows = [_row(hard, stride, phase) for phase in (0, 1)]
        if len(rows[0]) < MIN_ROW_BITS:
            break  # later strides only have shorter rows
        best: Stride | None = None
        for phase, row in enumerate(rows):
            w = syndrome_bits(row[None, :])[0]
            if len(w) == 0:
                continue
            rate = float(w.mean())
            z = (0.5 - rate) * 2.0 * np.sqrt(len(w))
            if best is None or rate < best.rate:
                best = Stride(stride, phase, rate, float(z), len(w))
        if best is not None:
            out.append(best)
    return out


def scan_strides(hard: NDArray[np.uint8]) -> tuple[Stride, ...]:
    """Strides whose rows satisfy the code's parity checks, best first. Empty for a stream with
    no such stride, or (structured, not interleaved) more than `MAX_STRIDES` of them."""
    hard = np.asarray(hard, np.uint8)[:MAX_BITS]
    found = [s for s in _stride_scan(hard) if s.z >= Z_STRIDE]
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
    return _fold_lengths(_row(np.asarray(hard, np.uint8)[:MAX_BITS], stride.stride, stride.phase))


def _fold_lengths(row: NDArray[np.uint8]) -> tuple[tuple[int, float], ...]:
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


HELIX_HYPOTHESES = 2 * sum(range(2, HELIX_BRUTE + 1)) + 2 * HELIX_PREFILTER * MAX_STRIDE
HELIX_STARTS = 24  # walks per (rows, column phase)


def helix_indices(
    rows: int, phases: NDArray[np.int64], starts: NDArray[np.int64], length: int
) -> NDArray[np.int64]:
    """Received-bit positions of walks through a helical interleaver of `rows` rows: each
    walk starts at a received position and follows the code stream, which advances by rows - 1
    bits, or by 2 rows - 1 from the first position of a column (position = column phase modulo
    rows). Shape (phases, starts, length)."""
    phi = phases[:, None, None]
    start = starts[None, :, None]
    k = np.arange(length, dtype=np.int64)[None, None, :]
    first = (start - phi) % rows  # the walk's offset into its column
    wraps = np.maximum(0, (k - first + rows - 1) // rows)
    return start + k * (rows - 1) + rows * wraps


def _helix_hypotheses(hard: NDArray[np.uint8], rows: int) -> list[tuple[int, float, float, int]]:
    """(column phase, mean syndrome rate, z, windows) of every column phase's walks for `rows`
    rows, best first; empty when the stream is too short for the walk.

    Each walk is a stretch of the code stream, but which bit of the code's pairs it starts on
    depends on the walk, so a walk is judged at the better of its two pairings; that choice
    biases a random walk's z up by the mean of the larger of two standard normals (1 / sqrt(pi))
    with variance 1 - 1 / pi, which the total z removes."""
    starts_n = min(rows, HELIX_STARTS)
    starts = (np.arange(starts_n, dtype=np.int64) * rows) // starts_n
    length = min(HELIX_WALK, (len(hard) - 2 * rows) // (2 * rows))
    if length < 24:
        return []
    index = helix_indices(rows, np.arange(rows, dtype=np.int64), starts, length)
    bits = hard[index.reshape(rows * starts_n, length)]
    z: list[Float] = []
    rate: list[Float] = []
    windows = 0
    for pairing in (0, 1):
        w = syndrome_bits(bits[:, pairing:])
        if w.shape[1] == 0:
            return []
        windows = w.shape[1]
        r = w.mean(axis=1).reshape(rows, starts_n)
        rate.append(r)
        z.append((0.5 - r) * 2.0 * float(np.sqrt(windows)))
    best = np.maximum(z[0], z[1])  # per (phase, walk)
    best_rate: Float = np.where(z[0] >= z[1], rate[0], rate[1])
    ones = bits.mean(axis=1).reshape(rows, starts_n).mean(axis=1)
    mean = 1.0 / float(np.sqrt(np.pi))
    total_z = (best.sum(axis=1) - mean * starts_n) / float(np.sqrt(starts_n * (1.0 - 1.0 / np.pi)))
    out = [
        (
            phase,
            float(best_rate[phase].mean()),
            float(total_z[phase]) if BALANCE[0] <= ones[phase] <= BALANCE[1] else 0.0,
            windows * starts_n,
        )
        for phase in range(rows)
    ]
    return sorted(out, key=lambda t: -t[2])


def find_helical(hard: NDArray[np.uint8]) -> tuple[BlindBlock, ...]:
    """Helical interleavers the structure of the stream names (at most two row lengths): the
    rows and column phase whose walks read the code's parity checks, then the row length where
    the failures fold. Empty when no walk beats chance by `Z_HELIX` at a plausible rate, or when
    walks of several row counts do equally (structure that is not interleaving)."""
    hard = np.asarray(hard, np.uint8)[:MAX_BITS]
    rows_to_try = list(range(2, HELIX_BRUTE + 1))
    scan = _stride_scan(hard)
    constant = {s.stride: s.rate for s in scan}
    ranked = sorted((s for s in scan if s.stride + 1 > HELIX_BRUTE), key=lambda s: s.rate)
    rows_to_try += [s.stride + 1 for s in ranked[:HELIX_PREFILTER]]
    hits: list[tuple[int, int, float, float, int]] = []
    for rows in rows_to_try:
        for phase, rate, z, windows in _helix_hypotheses(hard, rows)[:1]:
            # A block interleaver of R - 1 rows is read by the helix of R rows between its wraps:
            # a real helix beats the constant stride R - 1 clearly, a block does not.
            beats = rate < constant.get(rows - 1, 0.5) - HELIX_MARGIN
            if z >= Z_HELIX and rate < MAX_HELIX_RATE and beats:
                hits.append((rows, phase, rate, z, windows))
    if not hits:
        return ()
    hits.sort(key=lambda t: -t[3])
    rows, phase, rate, z, windows = hits[0]
    # A helix of R rows is also read, less well, by other row counts: refuse when one reads as
    # well as the best (a structured stream, not an interleaved one).
    if any(h[0] != rows and h[3] > 0.8 * z for h in hits[1:]):
        return ()
    k = np.arange(min(ROW_CAP, (len(hard) - phase) // rows), dtype=np.int64)
    walk = phase + k * (rows - 1) + rows * ((k + rows - 1) // rows)
    walk = hard[walk[walk < len(hard)]]
    # The row's own pairing: the one whose syndrome is lower.
    candidates = [walk[pairing:][: (len(walk) - pairing) // 2 * 2] for pairing in (0, 1)]
    row = min(candidates, key=lambda r: float(syndrome_bits(r[None, :])[0].mean()))
    pairing = 0 if row is candidates[0] else 1
    stride = Stride(rows, pairing, rate, float(z), windows)
    out: list[BlindBlock] = []
    for cols, fold_z in _fold_lengths(row):
        if rows * cols <= MAX_BLOCK:
            out.append(BlindBlock(Helical(rows, cols), stride, fold_z, phase))
    return tuple(out)


def find_blocks(hard: NDArray[np.uint8]) -> tuple[BlindBlock, ...]:
    """Block and helical interleavers the structure of the stream names, best first, at most
    `MAX_STRIDES * CANDIDATES_PER_STRIDE` of them (block candidates first)."""
    hard = np.asarray(hard, np.uint8)
    out: list[BlindBlock] = []
    for stride in scan_strides(hard):
        for cols, z in row_lengths(hard, stride):
            if stride.stride * cols <= MAX_BLOCK:
                out.append(BlindBlock(Block(stride.stride, cols), stride, z))
    helical = find_helical(hard)
    if helical:
        # A helix of R rows also reads as a block stride of R - 1, which is not a block.
        out = [b for b in out if b.stride.stride != helical[0].stride.stride - 1]
    out += helical
    return tuple(out[: MAX_STRIDES * CANDIDATES_PER_STRIDE])
