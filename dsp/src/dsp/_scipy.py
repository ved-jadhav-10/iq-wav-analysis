# pyright: basic
"""Typed wrappers for the few SciPy routines dsp/ uses.

SciPy's annotations are incomplete, which strict type checking rejects; this module is the one
place that calls SciPy directly, and every wrapper states the types it returns.
"""

from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy import fft, linalg, ndimage, signal, special, stats

Bool2D = NDArray[np.bool_]
Float = NDArray[np.float64]
Complex = NDArray[np.complex128]


def kaiser_lowpass(numtaps: int, cutoff: float, attenuation_db: float = 80.0) -> Float:
    """Linear-phase low-pass FIR; `cutoff` in cycles/sample (0 < cutoff < 0.5)."""
    beta = float(signal.kaiser_beta(attenuation_db))
    taps = signal.firwin(numtaps, cutoff, window=("kaiser", beta), fs=1.0)  # type: ignore[arg-type]
    return np.asarray(taps, np.float64)


def kaiser_taps(width: float, attenuation_db: float = 80.0) -> int:
    """Taps a Kaiser low-pass needs for a transition `width` in cycles/sample (odd)."""
    numtaps, _ = signal.kaiserord(attenuation_db, width * 2)
    return int(numtaps) | 1


def upfirdn(h: Float, x: NDArray[Any], down: int, up: int = 1) -> Complex:
    return np.asarray(signal.upfirdn(h, x, up=up, down=down), np.complex128)


def resample_poly(x: NDArray[Any], up: int, down: int) -> Complex:
    return np.asarray(signal.resample_poly(x, up, down), np.complex128)


def zoom_spectrum(x: NDArray[Any], f0: float, f1: float, points: int) -> Complex:
    """DTFT of x at `points` frequencies from f0 to f1 inclusive (cycles/sample)."""
    return np.asarray(signal.zoom_fft(x, [f0, f1], m=points, fs=1.0, endpoint=True), np.complex128)  # type: ignore[arg-type]


def label(mask: Bool2D) -> tuple[NDArray[np.int32], int]:
    result: Any = ndimage.label(mask, structure=np.ones((3, 3), bool))
    labels, count = result
    return np.asarray(labels, np.int32), int(count)


def find_objects(labels: NDArray[np.int32]) -> list[tuple[slice, slice]]:
    return [s for s in ndimage.find_objects(labels) if s is not None]


def closing(mask: Bool2D, rows: int, cols: int) -> Bool2D:
    structure = np.ones((rows, cols), bool)
    padded = np.pad(mask, ((rows, rows), (cols, cols)))
    closed = ndimage.binary_closing(padded, structure)
    return np.asarray(closed[rows:-rows, cols:-cols], np.bool_)


def percentile_filter(x: Float, percentile: float, size: int) -> Float:
    return np.asarray(ndimage.percentile_filter(x, percentile, size=size, mode="nearest"))


def gamma_ppf(q: float, shape: float) -> float:
    """Quantile of Gamma(shape, scale 1/shape): the mean of `shape` unit exponentials."""
    return float(stats.gamma.ppf(q, shape, scale=1.0 / shape))


def gamma_isf(p: float, shape: float) -> float:
    """Level exceeded with probability p by the mean of `shape` unit exponentials."""
    return float(stats.gamma.isf(p, shape, scale=1.0 / shape))


def gamma_sf(x: float, shape: float) -> float:
    """P(mean of `shape` unit exponentials > x)."""
    return float(special.gammaincc(shape, x * shape))


def binom_sf(k: NDArray[Any], n: int, p: float) -> Float:
    """P(X >= k) for X ~ Binomial(n, p), for each k (an array of counts)."""
    return np.asarray(stats.binom.sf(np.asarray(k) - 1, n, p), np.float64)


def norm_isf(p: float) -> float:
    return float(stats.norm.isf(p))


def eigvalsh(matrix: Complex) -> Float:
    """Eigenvalues of a Hermitian matrix, largest first."""
    return np.asarray(linalg.eigvalsh(matrix), np.float64)[::-1]


def hilbert(x: Float) -> Complex:
    return np.asarray(signal.hilbert(x), np.complex128)


def excess_kurtosis(x: Float) -> float:
    """Fisher (excess) kurtosis: 0 for a Gaussian, negative for a flatter, e.g. multimodal,
    distribution (an FSK signal's discrete tones), positive for a more sharply peaked one."""
    return float(stats.kurtosis(x, fisher=True, bias=False))


def log10_gamma_sf(x: float, shape: float) -> float:
    """log10 P(mean of `shape` unit exponentials > x), accurate far into the tail.

    Exact while the probability is representable; beyond that the Wilson-Hilferty cube-root
    normal approximation, whose log tail stays finite.
    """
    p = float(special.gammaincc(shape, x * shape))
    if p > 1e-280:
        return float(np.log10(p))
    v = 1.0 / (9.0 * shape)
    z = (np.cbrt(x) - (1.0 - v)) / np.sqrt(v)
    return float(special.log_ndtr(-z) / np.log(10.0))


def i0(x: Float) -> Float:
    """The modified Bessel function of order 0, compiled (numpy's `np.i0` is pure Python)."""
    return np.asarray(special.i0(x), np.float64)  # pyright: ignore[reportUnknownMemberType]


def autocorrelation(x: NDArray[Any]) -> Float:
    """Linear autocorrelation of a real sequence, lags 0 .. len(x) - 1, in single precision (a
    screen: the lag-r sums of +-1 values are exact to about 1e-6 of the length)."""
    n = len(x)
    size: Any = fft.next_fast_len(2 * n - 1, True)
    spectrum: Any = fft.rfft(np.asarray(x, np.float32), size)
    r: Any = fft.irfft(spectrum.real**2 + spectrum.imag**2, size)
    return np.asarray(r[:n], np.float64)
