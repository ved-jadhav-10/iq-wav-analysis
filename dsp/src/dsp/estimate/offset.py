"""The symbol rate of offset QPSK, from a pair of lines in x² (PLAN M3).

Offset QPSK delays Q by half a symbol, so I² and Q² peak half a symbol apart and |x|² = I² + Q²
has no symbol-rate line: `symbol_rate` finds none. x² = (I² - Q²) + 2jIQ does: I² - Q² swings
between I's peak and Q's, a periodic signal at the symbol rate R, and 2jIQ is periodic at 2R. A
carrier offset f moves everything by 2f, so x² shows lines at 2f - R and 2f + R, equally strong,
with nothing between them: R is half their spacing and f half their midpoint. (Plain QPSK has no
lines in x² at all, BPSK has one at 2f and others at 2f + kR with the strongest between the
pair, and an unmodulated carrier has a single line.)

Limits: the pair must lie inside one cycle per sample (a decimated channel keeps it there); a
pulse far from RRC-like weakens the lines; the carrier offset is known only modulo half a cycle
per sample (the smaller of the two is taken).
"""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from dsp.estimate.lines import Line, find_lines

PAIR_BALANCE = 0.4  # the weaker line's amplitude over the stronger's, at least
CENTRE_LIMIT = 1.0  # a line between the pair this strong (against the weaker) means BPSK


@dataclass(frozen=True)
class OffsetRate:
    normalised_rate: float  # symbols per channel sample
    uncertainty: float  # 1 sigma, symbols per channel sample
    cfo: float  # carrier offset, cycles per channel sample
    ratio: float  # the weaker line of the pair over its local spectrum level


def offset_symbol_rate(
    x: NDArray[np.complex128], low: float = 0.01, high: float = 0.5
) -> OffsetRate | None:
    """The symbol rate and carrier offset of an offset-QPSK signal, or None when x² shows no
    balanced pair of lines at a spacing between 2 * `low` and 2 * `high` cycles per sample."""
    search = find_lines(np.asarray(x, np.complex128) ** 2, -0.5, 0.5, max_lines=8)
    lines = sorted(search.lines, key=lambda line: line.frequency)
    best: tuple[float, Line, Line] | None = None
    for i, a in enumerate(lines):
        for b in lines[i + 1 :]:
            rate = (b.frequency - a.frequency) / 2
            if not low <= rate <= high:
                continue
            weak, strong = sorted((a.amplitude, b.amplitude))
            if weak < PAIR_BALANCE * strong:
                continue
            middle = (a.frequency + b.frequency) / 2
            if any(
                c is not a
                and c is not b
                and abs(c.frequency - middle) < 0.1 * rate
                and c.amplitude > CENTRE_LIMIT * weak
                for c in lines
            ):
                continue
            score = min(a.ratio, b.ratio)
            if best is None or score > best[0]:
                best = (score, a, b)
    if best is None:
        return None
    score, a, b = best
    middle = (a.frequency + b.frequency) / 4  # the carrier offset: half of x²'s midpoint
    cfo = middle if abs(middle) <= 0.25 else middle - math.copysign(0.5, middle)
    sigma = math.hypot(a.uncertainty, b.uncertainty) / 2
    return OffsetRate((b.frequency - a.frequency) / 2, sigma, cfo, score)
