"""The symbol rate of offset QPSK, from a pair of lines in x² (PLAN M3).

Offset QPSK delays Q by half a symbol, so I² and Q² peak half a symbol apart and |x|² = I² + Q²
has no symbol-rate line: `symbol_rate` finds none. x² = (I² - Q²) + 2jIQ does: I² - Q² swings
between I's peak and Q's, a periodic signal at the symbol rate R, and 2jIQ is periodic at 2R. A
carrier offset f moves everything by 2f, so x² shows lines at 2f - R and 2f + R, equally strong,
with nothing between them: R is half their spacing and f half their midpoint. (Plain QPSK has no
lines in x² at all, BPSK has one at 2f and others at 2f + kR with the strongest between the
pair, and an unmodulated carrier has a single line.)

Limits:
- The pair must lie inside one cycle per sample without wrapping: 2|f| + R < 0.5. A channelised
  signal sits near 0 Hz, so this holds. A wrapped pair looks like a pair at spacing 1 - 2R, a
  rate of 0.5 - R, which is why the rate is capped at 0.25 symbols per sample (four samples a
  symbol, the least the matched filter wants): a wide unchannelised recording with the signal
  far off centre then returns nothing rather than an aliased rate.
- The carrier must hold still: its drift moves the lines of x² twice as far as it moves the
  signal, and they smear out of a single FFT bin once the drift passes about 1 / (2 N²) cycles
  per sample² over N samples (3e-11 for 131,072 samples; a LEO pass's Doppler is far above that).
  Then nothing is found, and the signal is not recognised as offset QPSK.
- A pulse far from RRC-like, or a roll-off near 0.1, weakens the lines; the false-alarm
  threshold (`PAIR_ALPHA`) is strict, so weak pairs are missed, not guessed. The caller checks the
  rate against the signal's bandwidth (`dsp.analyse`), which a spurious pair at half the rate fails.
- The carrier offset is returned with its uncertainty and only when that is within
  `MAX_CFO_UNCERTAINTY`: `dsp.sync.recover_timing` sums the fourth power over blocks and unwraps
  its phase, which a carrier error beyond about 5e-5 cycles/sample turns into garbage symbols.
"""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from dsp.estimate.lines import Line, find_lines

PAIR_ALPHA = 1e-6  # false-alarm probability of the line search that the pair is taken from
PAIR_BALANCE = 0.4  # the weaker line's amplitude over the stronger's, at least
CENTRE_LIMIT = 3.0  # a line between the pair this many times the stronger of them means BPSK
MAX_CFO_UNCERTAINTY = 2e-5  # cycles/sample (1 sigma), for the timing that follows


@dataclass(frozen=True)
class OffsetRate:
    normalised_rate: float  # symbols per channel sample
    uncertainty: float  # 1 sigma, symbols per channel sample
    cfo: float  # carrier offset, cycles per channel sample
    ratio: float  # the weaker line of the pair over its local spectrum level
    cfo_uncertainty: float = 0.0  # 1 sigma, cycles per channel sample


def offset_symbol_rate(
    x: NDArray[np.complex128], low: float = 0.01, high: float = 0.25
) -> OffsetRate | None:
    """The symbol rate and carrier offset of an offset-QPSK signal, or None when x² shows no
    balanced pair of lines at a spacing between 2 * `low` and 2 * `high` cycles per sample, or the
    pair would wrap past half a cycle per sample, or the offset is not known well enough."""
    search = find_lines(np.asarray(x, np.complex128) ** 2, -0.5, 0.5, max_lines=8, alpha=PAIR_ALPHA)
    lines = sorted(search.lines, key=lambda line: line.frequency)
    best: tuple[float, Line, Line] | None = None
    for i, a in enumerate(lines):
        for b in lines[i + 1 :]:
            rate = (b.frequency - a.frequency) / 2
            if not low <= rate <= high:
                continue
            middle = (a.frequency + b.frequency) / 2
            if abs(middle) + rate >= 0.49:
                continue  # the pair would wrap past the edge of the band
            weak, strong = sorted((a.amplitude, b.amplitude))
            if weak < PAIR_BALANCE * strong:
                continue
            if any(
                c is not a
                and c is not b
                and abs(c.frequency - middle) < 0.1 * rate
                and c.amplitude > CENTRE_LIMIT * strong
                for c in lines
            ):
                continue
            score = min(a.ratio, b.ratio)
            if best is None or score > best[0]:
                best = (score, a, b)
    if best is None:
        return None
    score, a, b = best
    sigma = math.hypot(a.uncertainty, b.uncertainty)
    if sigma / 4 > MAX_CFO_UNCERTAINTY:
        return None
    cfo = (a.frequency + b.frequency) / 4  # half of x²'s midpoint: the pair's centre is 2f
    return OffsetRate((b.frequency - a.frequency) / 2, sigma / 2, cfo, score, sigma / 4)
