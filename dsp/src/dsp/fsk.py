"""Non-coherent 2-FSK demodulation to soft bits (PLAN M3).

1. The frequency discriminator: the phase step between successive samples, in cycles/sample.
2. Resampled to SPS samples per symbol at the rate from `fsk_symbol_rate`.
3. Timing from the transitions: a tone change can only happen on a symbol boundary, so the
   squared difference of the frequency is periodic at the symbol rate; its phase per block
   (Oerder-Meyr on |diff|² instead of |y|²), unwrapped, gives the boundaries.
4. Each symbol's value is the frequency averaged over its interior (the middle INTERIOR
   fraction), away from the transitions; the decision threshold is the median, which also
   removes any residual carrier offset for balanced data.

Mapping matches `dsp.synth.modulate.fsk`: bit 0 on the lower tone, bit 1 on the upper. An
inverted spectrum (I/Q swapped) inverts every bit, which the framing search's inverted-sync
check covers.
"""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from dsp.sync import interpolate

Complex = NDArray[np.complex128]
Float = NDArray[np.float64]

SPS = 8
TIMING_BLOCK = 256  # symbols
INTERIOR = 0.75  # the middle three quarters of each symbol are integrated


@dataclass(frozen=True)
class FskSymbols:
    values: Float  # per-symbol mean frequency about the threshold, cycles/channel sample
    llr: Float  # positive means bit 0 (the lower tone)
    shift: float  # tone spacing, cycles/channel sample
    centre: float  # the decision threshold (residual carrier offset), cycles/channel sample
    jitter: float  # RMS scatter of the block timing estimates, symbols


def demodulate(x: Complex, rate: float) -> FskSymbols:
    """2-FSK symbols from channel samples `x` at `rate` symbols per sample."""
    grid = np.arange(0.0, len(x) - 1, 1.0 / (SPS * rate))
    y = interpolate(x, grid)  # SPS samples per symbol from here on
    f = np.angle(y[1:] * np.conj(y[:-1])) / (2 * math.pi)
    edges = np.diff(f, prepend=f[0]) ** 2
    blocks = len(f) // (SPS * TIMING_BLOCK)
    if blocks < 2:
        raise ValueError(f"too few symbols for FSK timing ({len(f) // SPS})")
    folded = edges[: blocks * SPS * TIMING_BLOCK].reshape(blocks, TIMING_BLOCK, SPS).sum(axis=1)
    # The edge profile is a narrow spike, so its first harmonic alone (Oerder-Meyr) is weak;
    # take each block's spike position, relative to the whole burst's, to a fraction of a sample.
    anchor = _peak(folded.sum(axis=0))
    offsets = (np.array([_peak(p) for p in folded]) - anchor + SPS / 2) % SPS - SPS / 2
    boundary = (anchor + offsets) / SPS  # symbols
    centres = (np.arange(blocks) + 0.5) * TIMING_BLOCK
    keep = np.abs(offsets - np.median(offsets)) < SPS / 4  # blocks too noisy to place the spike
    trend = np.polyfit(centres[keep], boundary[keep], 1) if keep.sum() >= 2 else (0.0, anchor / SPS)
    jitter = float(np.std(boundary[keep] - np.polyval(trend, centres[keep])))
    boundary = np.polyval(trend, centres)
    # Tones from the discriminator's two clusters (per-sample, so noisy, but only their
    # medians are used).
    centre = float(np.median(f))
    upper, lower = f[f > centre], f[f <= centre]
    tones = (float(np.median(lower)), float(np.median(upper)))
    shift = tones[1] - tones[0]
    # Non-coherent detection: each symbol's energy at each tone, over its interior.
    count = len(y) // SPS - 2
    k = np.arange(count, dtype=np.float64)
    starts = SPS * (k + np.interp(k, centres, boundary)) + SPS * (1 - INTERIOR) / 2
    width = max(2, round(SPS * INTERIOR))
    first = np.floor(starts).astype(np.int64)
    ok = (first >= 0) & (first + width < len(y))
    index = first[ok][:, None] + np.arange(width)[None, :]
    segment = y[index]
    energies = [
        np.abs(np.sum(segment * np.exp(-2j * np.pi * tone * index), axis=1)) ** 2 for tone in tones
    ]
    e0, e1 = energies
    noise = float(np.median(np.minimum(e0, e1))) or 1e-12
    llr = (e0 - e1) / noise
    values = (e1 - e0) / np.maximum(e0 + e1, 1e-12) * shift / 2
    scale = SPS * rate  # cycles per resampled sample -> cycles per channel sample
    return FskSymbols(values, np.asarray(llr, np.float64), shift * scale, centre * scale, jitter)


def _peak(profile: Float) -> float:
    """The circular argmax of a folded profile, refined by a parabola through its neighbours."""
    k = int(np.argmax(profile))
    left, mid, right = profile[k - 1], profile[k], profile[(k + 1) % len(profile)]
    denom = left - 2 * mid + right
    return k + (0.5 * (left - right) / denom if denom < 0 else 0.0)
