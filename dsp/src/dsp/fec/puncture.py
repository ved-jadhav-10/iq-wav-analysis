"""Puncturing patterns for the K=7 rate-1/2 mother code, and depuncturing (PLAN M5).

A punctured code sends only some of the mother code's output bits. Patterns are the DVB-S ones
(ETSI EN 300 421), which CCSDS 131.0-B also lists for its K=7 code; rows are the branches X then
Y, columns the input bits of one period, 1 meaning the bit is sent. The stream order is time
major and branch minor, exactly as `dsp.synth.fec.Convolutional` writes it (tests check this
against that encoder). Depuncturing puts the received bits back at their mother-code positions
and a zero LLR, no information, where a bit was dropped, so the ordinary Viterbi decoder runs
unchanged (`dsp.fec.viterbi.decode`).

The stream may start anywhere in the pattern's period, so a *phase* says which of the period's
sent bits comes first: `kept` phases per pattern.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from dsp.fec.viterbi import K7_R12, ConvCode

Float = NDArray[np.float64]


@dataclass(frozen=True)
class Puncture:
    rate: str  # e.g. "3/4"
    pattern: tuple[tuple[int, ...], ...]  # rows = branches, columns = one period of input bits

    @property
    def period(self) -> int:
        return len(self.pattern[0])

    @property
    def sent(self) -> NDArray[np.int64]:
        """Mother-code positions (time major, branch minor) sent in one period."""
        flags = np.array(self.pattern, dtype=np.uint8).T.ravel()
        return np.flatnonzero(flags)

    @property
    def kept(self) -> int:
        """Bits sent per period, which is also the number of phases a stream can start at."""
        return len(self.sent)

    def code(self, mother: ConvCode = K7_R12) -> ConvCode:
        """The mother code labelled as this punctured rate (decode depunctured soft bits)."""
        gens = ",".join(f"{g:o}" for g in mother.generators)
        return ConvCode(
            f"Conv K={mother.constraint} r{self.rate} punctured ({gens})₈",
            mother.constraint,
            mother.generators,
        )


PUNCTURES: tuple[Puncture, ...] = (
    Puncture("2/3", ((1, 0), (1, 1))),
    Puncture("3/4", ((1, 0, 1), (1, 1, 0))),
    Puncture("5/6", ((1, 0, 1, 0, 1), (1, 1, 0, 1, 0))),
    Puncture("7/8", ((1, 0, 0, 0, 1, 0, 1), (1, 1, 1, 1, 0, 1, 0))),
)


def depuncture(llr: ArrayLike, puncture: Puncture, phase: int) -> Float:
    """The mother-rate soft stream for punctured soft bits `llr` that start `phase` sent bits
    into the pattern's period (0 <= phase < puncture.kept). Dropped positions are zero LLRs;
    the result starts on a period boundary and holds whole blocks of the mother code."""
    if not 0 <= phase < puncture.kept:
        raise ValueError(f"phase must be in 0 .. {puncture.kept - 1}")
    y = np.asarray(llr, dtype=np.float64)
    n = len(puncture.pattern)
    sent = puncture.sent
    index = phase + np.arange(len(y))
    positions = (index // puncture.kept) * (n * puncture.period) + sent[index % puncture.kept]
    length = -(-(int(positions[-1]) + 1) // n) * n if len(y) else 0
    out = np.zeros(length)
    out[positions] = y
    return out
