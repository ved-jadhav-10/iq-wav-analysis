"""A catalogue of standard block interleavers and their inverse (PLAN M5).

Sanket never claims to recover a general pseudo-random permutation (project rule) - only a
fixed, small catalogue: block (written by rows, read by columns) and helical (the same with
column c starting c rows down) interleavers at the sizes used elsewhere in this codebase
(`bench.presets`'s "LDPC(576) + block" and "conv 1/2 + block" chains, 24x48 and 16x36, and
`tests/dsp/test_synth_chain.py`'s round-trip cases, 8x12 and 8x255), both orientations of each
since a blind search can't know which axis was written first, and the IEEE 802.11 BCC
interleaver (IEEE 802.11 §17.3.5.7) for its four standard symbol sizes. Anything outside this
catalogue is UNKNOWN with its measured period (PLAN M5), not a guess.

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


Interleaver = Block | Helical | Wifi


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
