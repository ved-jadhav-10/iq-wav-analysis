"""PSK/QAM demapping to soft bits (PROTOTYPE_PLAN P1, P2).

Gray mappings match `dsp.synth.modulate` (copied here so product code doesn't import synth):
- BPSK: 0 -> +1, 1 -> -1.
- QPSK: bits (b0, b1) -> ((1 - 2 b0) + j (1 - 2 b1)) / sqrt 2.
- 8PSK: 3 bits, label L at phase position p where L = gray(p): exp(j 2 pi p / 8).
- 16QAM: the first two bits Gray-code the I level, the last two Q; levels -3, -1, 1, 3 over
  sqrt 10.

Symbols come from `dsp.sync.correct_carrier`, whose M-fold phase ambiguity is left open:
`rotations` lists the candidate rotations, each a hypothesis the decoder tries and the CRC
settles.
"""

import math
from dataclasses import dataclass
from functools import cache

import numpy as np
from numpy.typing import NDArray

Complex = NDArray[np.complex128]
Float = NDArray[np.float64]

# The M-th power used for carrier recovery; also the number of phase rotations to try.
ORDERS = {"BPSK": 2, "QPSK": 4, "8PSK": 8, "16QAM": 4}
BITS_PER_SYMBOL = {"BPSK": 1, "QPSK": 2, "8PSK": 3, "16QAM": 4}


def _gray_position(label: int) -> int:
    """Gray label -> its position (after `dsp.synth.modulate.gray_position`)."""
    p, shift = label, 1
    while shift < 8:
        p ^= p >> shift
        shift <<= 1
    return p


@cache
def _table(modulation: str) -> tuple[Complex, NDArray[np.uint8]]:
    """Every point of the constellation and the bits it carries, MSB first."""
    k = BITS_PER_SYMBOL[modulation]
    labels = np.arange(1 << k)
    if modulation == "BPSK":
        points = 1.0 - 2.0 * labels
    elif modulation == "QPSK":
        points = ((1 - 2 * (labels >> 1)) + 1j * (1 - 2 * (labels & 1))) / math.sqrt(2)
    elif modulation == "8PSK":
        points = np.exp(2j * np.pi * np.array([_gray_position(int(v)) for v in labels]) / 8)
    elif modulation == "16QAM":
        level = np.array([2 * _gray_position(v) - 3 for v in range(4)], np.float64)
        points = (level[labels >> 2] + 1j * level[labels & 3]) / math.sqrt(10)
    else:
        raise ValueError(f"unknown modulation {modulation!r}")
    bits = ((labels[:, None] >> np.arange(k - 1, -1, -1)[None, :]) & 1).astype(np.uint8)
    return np.asarray(points, np.complex128), bits


def ideal_points(modulation: str) -> Complex:
    return _table(modulation)[0]


def rotations(modulation: str) -> tuple[int, ...]:
    """The candidate rotations, in degrees, for the M-fold ambiguity."""
    order = ORDERS[modulation]
    return tuple(360 * k // order for k in range(order))


def rotate(symbols: Complex, degrees: int) -> Complex:
    return symbols * np.exp(1j * math.radians(degrees))


@dataclass(frozen=True)
class SoftBits:
    llr: Float  # positive means bit 0; one per bit, symbols in order, MSB first
    evm: float  # RMS error vector over RMS ideal point
    noise_variance: float  # per complex dimension pair, from the error vectors


def evm(symbols: Complex, modulation: str) -> tuple[float, float]:
    """EVM (RMS, relative to unit-RMS points) and the error vectors' variance."""
    points = ideal_points(modulation)
    nearest = points[np.argmin(np.abs(symbols[:, None] - points[None, :]), axis=1)]
    variance = float(np.mean(np.abs(symbols - nearest) ** 2))
    return math.sqrt(variance), variance


def demap(symbols: Complex, modulation: str) -> SoftBits:
    """Max-log LLRs on unit-RMS symbols with the noise variance estimated from the EVM:
    per bit, (distance² to the nearest point carrying a 1 - to the nearest carrying a 0) / σ²."""
    error, variance = evm(symbols, modulation)
    variance = max(variance, 1e-6)
    points, bits = _table(modulation)
    d = np.abs(symbols[:, None] - points[None, :]) ** 2
    llr = np.empty((len(symbols), bits.shape[1]))
    for i in range(bits.shape[1]):
        ones = bits[:, i] == 1
        llr[:, i] = d[:, ones].min(axis=1) - d[:, ~ones].min(axis=1)
    return SoftBits(np.asarray(llr.ravel() / variance, np.float64), error, variance)
