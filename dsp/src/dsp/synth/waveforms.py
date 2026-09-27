"""Seeded baseband waveforms with exact ground truth. Frequencies are in cycles per sample."""

from typing import Any

import numpy as np
from numpy.typing import NDArray

Complex = NDArray[np.complex128]


def awgn(rng: np.random.Generator, n: int, power: float = 1.0) -> Complex:
    """Circular complex white Gaussian noise with the given mean power."""
    scale = np.sqrt(power / 2)
    return scale * rng.standard_normal(n) + 1j * scale * rng.standard_normal(n)


def tone(n: int, frequency: float, phase: float = 0.0) -> Complex:
    return np.exp(1j * (2 * np.pi * frequency * np.arange(n) + phase))


def frequency_shift(x: NDArray[Any], frequency: float) -> Complex:
    return x * tone(len(x), frequency)


def rrc_taps(sps: int, rolloff: float, span: int = 16) -> NDArray[np.float64]:
    """Root-raised-cosine pulse over `span` symbols, unit energy."""
    if not 0 < rolloff <= 1:
        raise ValueError("rolloff must be in (0, 1]")
    t = np.arange(-span * sps // 2, span * sps // 2 + 1) / sps
    b = rolloff
    h = np.empty_like(t)
    for i, ti in enumerate(t):
        if ti == 0:
            h[i] = 1 + b * (4 / np.pi - 1)
        elif np.isclose(abs(ti), 1 / (4 * b)):
            h[i] = (
                b
                / np.sqrt(2)
                * (
                    (1 + 2 / np.pi) * np.sin(np.pi / (4 * b))
                    + (1 - 2 / np.pi) * np.cos(np.pi / (4 * b))
                )
            )
        else:
            h[i] = (np.sin(np.pi * ti * (1 - b)) + 4 * b * ti * np.cos(np.pi * ti * (1 + b))) / (
                np.pi * ti * (1 - (4 * b * ti) ** 2)
            )
    return h / np.sqrt(np.sum(h**2))


def psk_symbols(rng: np.random.Generator, count: int, order: int) -> Complex:
    """Unit-magnitude M-PSK symbols; for order 4 the constellation sits at ±45° and ±135°."""
    offset = np.pi / 4 if order == 4 else 0.0
    return np.exp(1j * (2 * np.pi * rng.integers(0, order, count) / order + offset))


def shape(symbols: NDArray[Any], sps: int, rolloff: float, span: int = 16) -> Complex:
    """RRC pulse-shape the symbols; symbol k peaks at sample k * sps + span * sps // 2."""
    up = np.zeros(len(symbols) * sps, dtype=np.complex128)
    up[::sps] = symbols
    return np.convolve(up, rrc_taps(sps, rolloff, span)) * np.sqrt(sps)


def fsk(rng: np.random.Generator, count: int, order: int, sps: int, deviation: float) -> Complex:
    """Continuous-phase M-FSK: tones at (2k - order + 1) * deviation for symbol k."""
    symbols = rng.integers(0, order, count)
    freq = np.repeat((2 * symbols - order + 1) * deviation, sps)
    return np.exp(2j * np.pi * np.cumsum(freq))
