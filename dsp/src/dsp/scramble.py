"""Descramblers for the decoded bit stream (PLAN M6).

Two families, both linear over GF(2):

- **Additive** (synchronous): the data is XORed with the output of an LFSR that restarts at a
  fixed point of every frame, so every frame is XORed with the same sequence. CCSDS 131.0-B's
  pseudo-randomiser is one (h(x) = x^8 + x^7 + x^5 + x^3 + 1, all ones at the start of each
  frame's data after the sync marker, sequence FF 48 0E C0 ...).
- **Self-synchronising** (multiplicative): each output bit is the input XORed with earlier
  *received* bits, applied to the whole stream, sync word included. The G3RUH scrambler used by
  9600 bit/s amateur packet, 1 + x^12 + x^17, is one; descrambling is feed-forward, so a start
  in mid-stream is right after 17 bits.

Which one, if either, is not asked of the samples: each is one hypothesis in the search, decided
by the frame check. IEEE 802.11's x^7 + x^4 + 1 has a per-frame seed and is not catalogued here.
`dsp.synth.bits` has its own generator of these, kept apart so the tests compare two
implementations.
"""

from dataclasses import dataclass
from functools import cache
from typing import Literal

import numpy as np
from numpy.typing import NDArray

Bits = NDArray[np.uint8]


@cache
def _lfsr(taps: tuple[int, ...], seed: int, n: int) -> Bits:
    """The additive LFSR's first `n` bits (cached: every frame of a stream asks for the same)."""
    degree = taps[0]
    state = [(seed >> (degree - 1 - i)) & 1 for i in range(degree)]
    out = np.empty(n, np.uint8)
    for k in range(n):
        out[k] = state[0]
        feedback = state[0]
        for t in taps[1:]:
            feedback ^= state[t]
        state = [*state[1:], feedback]
    out.setflags(write=False)
    return out


@dataclass(frozen=True)
class Descrambler:
    name: str
    kind: Literal["additive", "self-sync"]
    # Exponents of the feedback polynomial other than the constant term, highest first.
    taps: tuple[int, ...]
    seed: int = 0  # additive only: the register at the start of each frame, most significant first

    def sequence(self, n: int) -> Bits:
        """The additive LFSR's first `n` output bits."""
        return _lfsr(self.taps, self.seed, n)

    def frame(self, body: Bits) -> Bits:
        """Descramble one frame's data (after the sync word) with the register restarted."""
        if self.kind != "additive":
            raise ValueError(f"{self.name} is applied to the whole stream, not to a frame")
        return np.asarray(body, np.uint8) ^ self.sequence(len(body))

    def stream(self, bits: Bits) -> Bits:
        """Descramble a whole stream. Only meaningful for a self-synchronising scrambler: the
        first `degree` bits of it lack the history they need and come out wrong."""
        if self.kind != "self-sync":
            raise ValueError(f"{self.name} restarts at each frame; use `frame`")
        x = np.asarray(bits, np.uint8)
        out = x.copy()
        for lag in self.taps[1:]:
            out[lag:] ^= x[:-lag]
        out[self.taps[0] :] ^= x[: -self.taps[0]]
        return out


CCSDS = Descrambler("CCSDS pseudo-randomiser", "additive", (8, 7, 5, 3), 0xFF)
G3RUH = Descrambler("G3RUH", "self-sync", (17, 12))
DESCRAMBLERS: tuple[Descrambler, ...] = (CCSDS, G3RUH)
