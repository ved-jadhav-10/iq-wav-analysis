"""A catalogue of standard block interleavers and their inverse (PROTOTYPE_PLAN P2).

Sanket never claims to recover a general pseudo-random permutation (project rule) - only a
fixed, small catalogue of standard block sizes actually used elsewhere in this codebase:
`bench.presets`'s "LDPC(576) + block" and "conv 1/2 + block" chains (24x48, 16x36) and
`tests/dsp/test_synth_chain.py`'s round-trip cases (8x12, 8x255). Both orientations of each
size are included, since a blind search can't know which axis was written first. Anything
outside this catalogue is UNKNOWN with its measured period (PLAN M5), not a guess.

`Block`'s permutation and `deinterleave`'s indexing are copied from
`dsp/src/dsp/synth/interleave.py`'s `Block`/`deinterleave` (with this comment as the
attribution), so a synth-generated block-interleaved stream inverts exactly; `dsp.synth` itself
must not be imported by product code (project rule).
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


def _catalogue() -> tuple[Block, ...]:
    sizes = ((24, 48), (16, 36), (8, 12), (8, 255))
    out: list[Block] = []
    for rows, cols in sizes:
        out.append(Block(rows, cols))
        if rows != cols:
            out.append(Block(cols, rows))
    return tuple(out)


CATALOGUE: tuple[Block, ...] = _catalogue()


def deinterleave(x: NDArray[Any], entry: Block, alignment: int = 0) -> NDArray[Any]:
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
