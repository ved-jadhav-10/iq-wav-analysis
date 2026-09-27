"""Channelisation: one detection's band mixed to 0 Hz, low-pass filtered and decimated (M2).

The band is widened by MARGIN on each side, and the output rate is at least OVERSAMPLE times
that width, so estimators see the signal with guard bands of noise around it. The filter is a
linear-phase Kaiser FIR (80 dB stopband) whose passband ends at 40 % of the output rate and
whose stopband starts at its Nyquist frequency; filtering and decimation run chunk by chunk,
with the filter state carried across chunks, so memory stays bounded.

The output keeps the noise density of the input: white noise of density N (per unit normalised
frequency at the input rate) reads N / D at the output rate, D the decimation. A real-valued
input's negative-frequency image is removed by the filter, so its output is the analytic
(positive-frequency) signal: the channel of a real recording carries half its power.

Estimators take at most `max_samples` output samples, from the start of the detection; the
number used is stated with every estimate.
"""

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dsp import _scipy
from dsp.detect import Detection

Complex = NDArray[np.complex128]

OVERSAMPLE = 4.0
MARGIN = 0.25  # of the detected bandwidth, added on each side
PASSBAND = 0.4  # of the output rate
MAX_SAMPLES = 1 << 18
READ_CHUNK = 1 << 18


@dataclass(frozen=True)
class Channel:
    samples: Complex
    centre: float  # the input frequency mixed to 0 Hz, cycles/sample
    decimation: int  # input samples per output sample
    start: int  # the input sample the output starts at
    passband: float  # one-sided, in cycles per output sample

    @property
    def input_samples(self) -> int:
        return len(self.samples) * self.decimation

    def to_input(self, frequency: float) -> float:
        """An output frequency (cycles/output sample) as an input frequency offset."""
        return frequency / self.decimation


def decimation_for(bandwidth: float) -> int:
    width = bandwidth * (1 + 2 * MARGIN)
    return max(1, math.floor(1.0 / (OVERSAMPLE * width)))


def channelise(
    source: Any,
    detection: Detection,
    *,
    max_samples: int = MAX_SAMPLES,
    centre: float | None = None,
) -> Channel:
    """The detection's band at baseband, from `detection.start` for at most `max_samples`."""
    d = decimation_for(detection.bandwidth)
    f0 = detection.centre if centre is None else centre
    start = detection.start
    stop = min(detection.stop, start + max_samples * d)
    is_real = not np.iscomplexobj(np.asarray(source.read(start, min(1, stop - start))))
    if d == 1 and not is_real:
        # A complex source has no negative-frequency mirror to remove, so a plain mix suffices.
        x = np.asarray(source.read(start, stop - start)).astype(np.complex128)
        n = np.arange(start, start + len(x))
        return Channel(x * np.exp(-2j * np.pi * f0 * n), f0, 1, start, 0.5)
    # A real source's mirror at -f0 must be removed by the low-pass below, so this always
    # filters when is_real, even at d == 1 (no decimation, filtering only).
    taps = _scipy.kaiser_taps(0.1 / d)
    h = _scipy.kaiser_lowpass(taps, 0.45 / d)
    delay = (taps - 1) // 2
    count = (stop - start) // d
    history_len = -(-(taps - 1) // d) * d  # a multiple of d, so outputs stay on the grid
    # The causal filter output at input index start + delay + q d is output q, centred on
    # start + q d. Reading starts there, with the history before it taken from the file.
    first = start + delay
    history = _read(source, first - history_len, history_len, f0)
    parts: list[Complex] = []
    chunk = max(d, READ_CHUNK - READ_CHUNK % d)
    end = first + count * d
    for s in range(first, end, chunk):
        n = min(chunk, end - s)
        block = np.concatenate([history, _read(source, s, n, f0)])
        z = _scipy.upfirdn(h, block, down=d)
        parts.append(z[history_len // d : history_len // d + -(-n // d)])
        history = block[-history_len:]
    y = np.concatenate(parts)[:count] if parts else np.zeros(0, np.complex128)
    return Channel(y, f0, d, start, PASSBAND)


def _read(source: Any, start: int, count: int, f0: float) -> Complex:
    """Samples [start, start + count) mixed down by f0, zero outside the recording."""
    out = np.zeros(count, np.complex128)
    lo, hi = max(0, start), min(int(source.num_samples), start + count)
    if hi > lo:
        out[lo - start : hi - start] = np.asarray(source.read(lo, hi - lo))
    return out * np.exp(-2j * np.pi * f0 * np.arange(start, start + count))
