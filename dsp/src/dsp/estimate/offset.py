"""The symbol rate of offset QPSK and of MSK/GMSK, from a pair of lines in x² (PLAN M3).

Offset QPSK delays Q by half a symbol, so I² and Q² peak half a symbol apart and |x|² = I² + Q²
has no symbol-rate line: `symbol_rate` finds none. x² = (I² - Q²) + 2jIQ does: I² - Q² swings
between I's peak and Q's, a periodic signal at the symbol rate R, and 2jIQ is periodic at 2R. A
carrier offset f moves everything by 2f, so x² shows lines at 2f - R and 2f + R, equally strong,
with nothing between them: R is half their spacing and f half their midpoint. (Plain QPSK has no
lines in x² at all, BPSK has one at 2f and others at 2f + kR with the strongest between the
pair, and an unmodulated carrier has a single line.)

MSK and GMSK (AIS) are 2-FSK with a modulation index of one half: their two tones are R / 2 apart,
so squaring leaves two lines R apart, and the symbol rate is the spacing (`msk_symbol_rate`). That
rests on the index being one half, which is a convention and is reported as one; the same pair
also comes from any 2-FSK with another index (index h gives a spacing of 2hR), so the caller
keeps it only when the tone-transition comb has not already explained it. The Gaussian
filter of GMSK smears the transitions the comb needs, but not these lines.

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
from dsp.estimate.params import SymbolRate

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


@dataclass(frozen=True)
class LinePair:
    spacing: float  # between the two lines, cycles/sample
    middle: float  # of x²: twice the carrier offset
    sigma: float  # 1 sigma of the spacing
    ratio: float  # the weaker line over its local spectrum level


def line_pair(
    x: NDArray[np.complex128], low: float, high: float, divisor: float
) -> LinePair | None:
    """The strongest balanced pair of lines in x² whose spacing over `divisor` is between `low`
    and `high` (the symbol rate it implies), and which does not wrap past the band's edge."""
    search = find_lines(np.asarray(x, np.complex128) ** 2, -0.5, 0.5, max_lines=8, alpha=PAIR_ALPHA)
    lines = sorted(search.lines, key=lambda line: line.frequency)
    best: tuple[float, Line, Line] | None = None
    for i, a in enumerate(lines):
        for b in lines[i + 1 :]:
            spacing = b.frequency - a.frequency
            if not low <= spacing / divisor <= high:
                continue
            middle = (a.frequency + b.frequency) / 2
            if abs(middle) + spacing / 2 >= 0.49:
                continue  # the pair would wrap past the edge of the band
            weak, strong = sorted((a.amplitude, b.amplitude))
            if weak < PAIR_BALANCE * strong:
                continue
            if any(
                c is not a
                and c is not b
                and abs(c.frequency - middle) < 0.05 * spacing
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
    return LinePair(
        b.frequency - a.frequency,
        (a.frequency + b.frequency) / 2,
        math.hypot(a.uncertainty, b.uncertainty),
        score,
    )


def offset_symbol_rate(
    x: NDArray[np.complex128], low: float = 0.01, high: float = 0.25
) -> OffsetRate | None:
    """The symbol rate and carrier offset of an offset-QPSK signal, or None when x² shows no
    balanced pair of lines at a spacing between 2 * `low` and 2 * `high` cycles per sample, or the
    pair would wrap past half a cycle per sample, or the offset is not known well enough."""
    pair = line_pair(x, low, high, 2.0)
    if pair is None or pair.sigma / 4 > MAX_CFO_UNCERTAINTY:
        return None
    return OffsetRate(pair.spacing / 2, pair.sigma / 2, pair.middle / 2, pair.ratio, pair.sigma / 4)


def msk_symbol_rate(
    x: NDArray[np.complex128], low: float = 0.01, high: float = 0.25
) -> SymbolRate | None:
    """The symbol rate of an MSK or GMSK signal: the spacing of the pair of lines in x², on the
    convention that the modulation index is one half (see the module docstring), which the
    result states in `assumption`. None when x² shows no such pair."""
    pair = line_pair(x, low, high, 1.0)
    if pair is None:
        return None
    return SymbolRate(
        pair.spacing,
        pair.sigma,
        pair.ratio,
        "modulation index 0.5 (MSK/GMSK: the two tones are half a symbol rate apart, so the "
        "lines of x squared are one symbol rate apart); another index gives another rate",
    )
