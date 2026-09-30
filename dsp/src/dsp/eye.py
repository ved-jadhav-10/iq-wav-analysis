"""Eye diagram data for a linear signal (PLAN M3): traces of the matched-filter output around a
spread of symbols, after carrier correction, ready to overlay.

The matched filter runs at `dsp.sync.SPS` samples per symbol; each trace is read from it at
`EYE_SPS` points per symbol by the same sinc interpolation, from one symbol before to one after
the symbol instant the timing loop found. Each trace is turned by the rotation the accepted
carrier correction gave its symbol, so the I trace shows the levels the demapper saw and the Q
trace the other axis. A wide-open eye is a clean signal with good timing; where it closes is
where noise, intersymbol interference or a timing error is.
"""

import math

import numpy as np
from numpy.typing import NDArray

from dsp.report import Eye
from dsp.sync import SPS, Timing, interpolate

EYE_SPS = 8  # points per symbol in each trace
EYE_TRACES = 200
MIN_SYMBOLS = 64

Complex = NDArray[np.complex128]


def eye_diagram(timing: Timing, corrected: Complex) -> Eye | None:
    """The eye of `timing`'s symbols, each turned as `corrected` (the carrier-corrected symbols,
    same order and length as `timing.symbols`) is turned from them; None if there are too few."""
    n = len(timing.symbols)
    if n < MIN_SYMBOLS or len(corrected) != n or timing.matched.size == 0:
        return None
    pick = np.unique(np.linspace(4, n - 5, min(EYE_TRACES, n - 8)).astype(np.int64))
    offsets = np.linspace(-1.0, 1.0, 2 * EYE_SPS + 1)
    times = timing.instants[pick][:, None] + SPS * offsets[None, :]
    traces = interpolate(timing.matched, times.ravel(), anti_alias=False).reshape(times.shape)
    turn = corrected[pick] / timing.symbols[pick]
    traces = traces * (turn / np.maximum(np.abs(turn), 1e-12))[:, None]
    scale = math.sqrt(float(np.mean(np.abs(traces[:, EYE_SPS]) ** 2))) or 1.0
    traces = traces / scale
    return Eye(
        samples_per_symbol=EYE_SPS,
        i=tuple(tuple(round(float(v), 3) for v in row) for row in traces.real),
        q=tuple(tuple(round(float(v), 3) for v in row) for row in traces.imag),
    )
