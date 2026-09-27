"""Discrete spectral lines in a sequence: found, tested for significance and refined.

Cyclostationary estimators (symbol rate from |x|^2, carrier from x^M, FSK rate from frequency
transitions, an AM carrier) all come down to a line in the spectrum of some function of the
samples. A line is tested against the local level of the spectrum around it: in a continuous
spectrum each periodogram bin is an exponential variable about that level, so a bin r times
the level has tail probability exp(-r). The threshold is Bonferroni-corrected over every bin
searched (counted as independent bins, half the zero-padded ones) and every sequence searched.

A significant line is refined by a zoom DTFT around its bin (for |x|^2 this is the cyclic
autocorrelation at lag zero, maximised over the cycle frequency) with parabolic interpolation,
and its standard uncertainty is the Cramer-Rao bound for one tone in white noise at the line's
measured strength: sqrt(6 / r) / (2 pi N), N the sequence length and r the peak over the level.

Limits: the level around a line is a block median, so two lines closer than a block (1/64 of
the band searched) share a level; the bound assumes the spectrum around the line is flat.
"""

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dsp import _scipy

Float = NDArray[np.float64]
LEVEL_BLOCK = 64  # bins per block for the local median level
ZOOM_POINTS = 65


@dataclass(frozen=True)
class Line:
    frequency: float  # cycles/sample of the analysed sequence
    uncertainty: float  # standard uncertainty, cycles/sample
    ratio: float  # peak bin over the local level
    log10_p: float  # log10 of a single bin's chance of reaching it
    amplitude: float  # |mean(e exp(-j 2 pi f n))|

    def significant(self, threshold: float) -> bool:
        return self.ratio > threshold


@dataclass(frozen=True)
class LineSearch:
    lines: tuple[Line, ...]  # significant lines, strongest first
    bins: int  # independent bins searched
    threshold: float  # the ratio a line needed

    @property
    def strongest(self) -> Line | None:
        return self.lines[0] if self.lines else None


def _spectrum(e: NDArray[Any]) -> tuple[NDArray[np.complex128], Float, int]:
    n = len(e)
    nfft = 1 << (max(n, 2) - 1).bit_length() + 1  # at least 2x zero padding
    spectrum = np.fft.fft(e, nfft)
    freqs = np.fft.fftfreq(nfft)
    return spectrum, freqs, nfft


def _level(power: Float) -> Float:
    """Local mean level of an exponential-like spectrum: block medians / ln 2, interpolated."""
    n = len(power)
    blocks = max(1, n // LEVEL_BLOCK)
    usable = blocks * LEVEL_BLOCK if n >= LEVEL_BLOCK else n
    med = np.median(power[:usable].reshape(blocks, -1), axis=1) / math.log(2)
    centres = (np.arange(blocks) + 0.5) * (usable / blocks)
    return np.interp(np.arange(n), centres, np.maximum(med, 1e-300))


def find_lines(
    e: NDArray[Any],
    low: float,
    high: float,
    *,
    sequences: int = 1,
    alpha: float = 0.01,
    max_lines: int = 8,
    exclude: tuple[tuple[float, float], ...] = (),
) -> LineSearch:
    """Significant lines of `e` (mean removed) with frequency in [low, high].

    For a real `e` pass a non-negative band; the mirror half is redundant. `sequences` is how
    many sequences the caller searches in total, for the Bonferroni correction.
    """
    x = np.asarray(e, np.complex128)
    x = x - x.mean()
    n = len(x)
    if n < 16 or high <= low:
        return LineSearch((), 0, math.inf)
    spectrum, freqs, nfft = _spectrum(x)
    order = np.argsort(freqs)
    freqs, spectrum = freqs[order], spectrum[order]
    power = spectrum.real**2 + spectrum.imag**2
    inside = (freqs >= low) & (freqs <= high)
    for a, b in exclude:
        inside &= ~((freqs >= a) & (freqs <= b))
    band = np.flatnonzero(inside)
    if len(band) < 3:
        return LineSearch((), 0, math.inf)
    # The level comes from the band searched, widened so short bands still have blocks.
    pad = LEVEL_BLOCK * 4
    lo, hi = max(0, band[0] - pad), min(len(power), band[-1] + pad + 1)
    level = np.empty_like(power)
    level[lo:hi] = _level(power[lo:hi])
    ratio = power[band] / level[band]
    independent = max(1, len(band) * n // nfft)
    threshold = math.log(independent * sequences / alpha)
    peaks = [
        int(band[i])
        for i in range(len(band))
        if ratio[i] > threshold
        and (i == 0 or ratio[i] >= ratio[i - 1])
        and (i == len(band) - 1 or ratio[i] >= ratio[i + 1])
    ]
    peaks.sort(key=lambda k: -power[k] / level[k])
    found: list[Line] = []
    step = 1.0 / nfft
    for k in peaks:
        if any(abs(freqs[k] - line.frequency) < 2.0 / n for line in found):
            continue
        r = float(power[k] / level[k])
        f = _refine(x, float(freqs[k]), step)
        amplitude = float(np.abs(np.mean(x * np.exp(-2j * np.pi * f * np.arange(n)))))
        sigma = math.sqrt(6.0 / r) / (2 * math.pi * n)
        found.append(Line(f, sigma, r, -r / math.log(10), amplitude))
        if len(found) >= max_lines:
            break
    return LineSearch(tuple(found), independent, threshold)


def _refine(x: NDArray[np.complex128], f: float, step: float) -> float:
    """The frequency of the DTFT peak within one FFT bin either side, parabolic-interpolated."""
    grid = np.linspace(f - step, f + step, ZOOM_POINTS)
    mag = np.abs(_scipy.zoom_spectrum(x, float(grid[0]), float(grid[-1]), ZOOM_POINTS))
    i = int(np.argmax(mag))
    if 0 < i < ZOOM_POINTS - 1:
        a, b, c = np.log(mag[i - 1 : i + 2] + 1e-300)
        denominator = a - 2 * b + c
        shift = 0.5 * (a - c) / denominator if denominator < 0 else 0.0
        return float(grid[i] + shift * (grid[1] - grid[0]))
    return float(grid[i])
