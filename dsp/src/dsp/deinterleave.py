"""A catalogue of standard block interleavers and their inverse (PLAN M5).

Sanket never claims to recover a general pseudo-random permutation (project rule) - only a
fixed, small catalogue: block (written by rows, read by columns) and helical (the same with
column c starting c rows down) interleavers at the sizes used elsewhere in this codebase
(`bench.presets`'s "LDPC(576) + block" and "conv 1/2 + block" chains, 24x48 and 16x36, and
`tests/dsp/test_synth_chain.py`'s round-trip cases, 8x12 and 8x255), both orientations of each
since a blind search can't know which axis was written first, the IEEE 802.11 BCC
interleaver (IEEE 802.11 §17.3.5.7) for its four standard symbol sizes, and the LTE turbo QPP
interleaver at the table entries listed in `QPP_TABLE`. Convolutional (Forney) interleavers have
no block boundary and are a separate grid (`FORNEY_CATALOGUE`, `deinterleave_forney`). Anything
outside these is UNKNOWN with its measured period (PLAN M5), not a guess.

The permutations and `deinterleave`'s indexing are copied from
`dsp/src/dsp/synth/interleave.py` (with this comment as the attribution), so a synth-generated
stream inverts exactly; `dsp.synth` itself must not be imported by product code (project rule).
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class Block:
    """rows x cols: written row by row, read column by column (matches
    `dsp.synth.interleave.Block`)."""

    rows: int
    cols: int

    @property
    def size(self) -> int:
        return self.rows * self.cols

    def permutation(self) -> NDArray[np.int64]:
        """out[j] = in[permutation[j]]."""
        return np.arange(self.size).reshape(self.rows, self.cols).T.ravel()

    @property
    def label(self) -> str:
        return f"block {self.rows}x{self.cols}"


@dataclass(frozen=True)
class Helical:
    """rows x cols, helical (diagonal): written by rows, read by columns with column c starting
    c rows down and wrapping (matches `dsp.synth.interleave.Helical`)."""

    rows: int
    cols: int

    @property
    def size(self) -> int:
        return self.rows * self.cols

    def permutation(self) -> NDArray[np.int64]:
        """out[j] = in[permutation[j]]."""
        c = np.repeat(np.arange(self.cols), self.rows)
        r = (np.tile(np.arange(self.rows), self.cols) + c) % self.rows
        return r * self.cols + c

    @property
    def label(self) -> str:
        return f"helical {self.rows}x{self.cols}"


@dataclass(frozen=True)
class Wifi:
    """The IEEE 802.11 BCC interleaver for one OFDM symbol of `n_cbps` coded bits, `n_bpsc` bits
    per subcarrier (matches `dsp.synth.interleave.Wifi`)."""

    n_cbps: int
    n_bpsc: int

    @property
    def size(self) -> int:
        return self.n_cbps

    def permutation(self) -> NDArray[np.int64]:
        """out[j] = in[permutation[j]]."""
        n, s = self.n_cbps, max(self.n_bpsc // 2, 1)
        k = np.arange(n)
        i = (n // 16) * (k % 16) + k // 16
        j = s * (i // s) + (i + n - (16 * i) // n) % s
        perm = np.empty(n, dtype=np.int64)
        perm[j] = k
        return perm

    @property
    def label(self) -> str:
        return f"802.11 N_CBPS {self.n_cbps}"


@dataclass(frozen=True)
class Qpp:
    """The LTE turbo code's quadratic permutation polynomial interleaver of length `k`,
    pi(i) = (f1 i + f2 i^2) mod k (3GPP TS 36.212 §5.1.3.2.3; matches
    `dsp.synth.interleave.Qpp`)."""

    k: int
    f1: int
    f2: int

    @property
    def size(self) -> int:
        return self.k

    def permutation(self) -> NDArray[np.int64]:
        """out[j] = in[permutation[j]]."""
        i = np.arange(self.k, dtype=np.int64)
        p = (self.f1 * i + self.f2 * i * i) % self.k
        if len(np.unique(p)) != self.k:
            raise ValueError(f"QPP ({self.f1}, {self.f2}) isn't a permutation of {self.k}")
        return p

    @property
    def label(self) -> str:
        return f"LTE QPP K={self.k}"


Interleaver = Block | Helical | Wifi | Qpp


# 3GPP TS 36.212 Table 5.1.3-3, the entries this catalogue carries: the eight shortest block
# sizes and the longest. The rest of the table is not entered from memory; each is added with its
# source when checked against the specification.
QPP_TABLE = (
    (40, 3, 10),
    (48, 7, 12),
    (56, 19, 42),
    (64, 7, 16),
    (72, 7, 18),
    (80, 11, 20),
    (88, 5, 22),
    (96, 11, 24),
    (6144, 263, 480),
)


def _catalogue() -> tuple[Interleaver, ...]:
    sizes = ((24, 48), (16, 36), (8, 12), (8, 255))
    out: list[Interleaver] = []
    for shape in (Block, Helical):
        for rows, cols in sizes:
            out.append(shape(rows, cols))
            if rows != cols:
                out.append(shape(cols, rows))
    # IEEE 802.11 §17.3.5.7: BPSK, QPSK, 16-QAM, 64-QAM at 48 data subcarriers.
    out += [Wifi(48, 1), Wifi(96, 2), Wifi(192, 4), Wifi(288, 6)]
    out += [Qpp(*row) for row in QPP_TABLE]
    return tuple(out)


CATALOGUE: tuple[Interleaver, ...] = _catalogue()


def deinterleave(x: NDArray[Any], entry: Interleaver, alignment: int = 0) -> NDArray[Any]:
    """Undo `entry`'s block interleaver on `x` (soft LLRs or hard bits/bytes alike), after
    dropping `alignment` leading elements - a real capture starts mid-stream, same as
    `dsp.synth.chain.SignalSpec.stream_offset`. Elements past the last whole block are dropped
    (they belong to a block the capture doesn't complete); the caller re-slices with a
    different `alignment` to try other phases.

    Matches `dsp.synth.interleave.deinterleave(x, entry)` exactly once `x` starts on a block
    boundary - `entry.deinterleave(x[alignment : alignment + n_whole_blocks * entry.size])` is
    the exact inverse of `entry.interleave` applied to that slice.
    """
    x = np.asarray(x)
    aligned = x[alignment:]
    whole = (len(aligned) // entry.size) * entry.size
    body = aligned[:whole]
    if whole == 0:
        return body
    out = np.empty_like(body.reshape(-1, entry.size))
    out[:, entry.permutation()] = body.reshape(-1, entry.size)
    return out.ravel()


@dataclass(frozen=True)
class Forney:
    """A convolutional (Forney) interleaver of `branches` (I) lanes with delay step `step` (M):
    element t goes to lane t mod I, which delays it by (t mod I) * M lane elements (matches
    `dsp.synth.interleave.Convolutional`). It has no block boundary, only a lane phase, and its
    inverse (lane b delayed by (I - 1 - b) * M) lags the input by `lag` elements, the first of
    which are the delay lines' start-up zeros."""

    branches: int
    step: int

    @property
    def lag(self) -> int:
        return (self.branches - 1) * self.branches * self.step

    @property
    def label(self) -> str:
        return f"convolutional I={self.branches} M={self.step}"


# A small generic grid: every lane count and step a bit-level interleaver in front of a short
# code is likely to use. The byte-level ones of DVB (12, 17) and J.83 sit after the inner decoder
# and are scored by the outer code instead.
FORNEY_CATALOGUE: tuple[Forney, ...] = tuple(
    Forney(i, m) for i in (2, 3, 4, 5, 6, 8) for m in (1, 2, 3, 4, 6, 8)
)


def deinterleave_forney(x: NDArray[Any], entry: Forney, phase: int = 0) -> NDArray[Any]:
    """Undo `entry` on `x` after dropping `phase` leading elements (which lane comes first is not
    known blind). The first `entry.lag` elements of the result are start-up filler (zeros, which
    are erasures for soft bits) and belong to no transmitted element; the caller drops them."""
    x = np.asarray(x)[phase:]
    out = np.zeros_like(x)
    for b in range(entry.branches):
        lane = x[b :: entry.branches]
        d = (entry.branches - 1 - b) * entry.step
        out[b :: entry.branches] = np.concatenate([np.zeros(d, x.dtype), lane])[: len(lane)]
    return out
