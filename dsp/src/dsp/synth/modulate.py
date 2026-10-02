"""Bits to baseband samples: Gray-mapped PSK/QAM, continuous-phase FSK, analog AM/FM, pulse
shaping, and fractional resampling for non-integer samples per symbol and clock drift.

Mappings (unit average symbol energy, Gray-coded so neighbours differ in one bit):
- BPSK: 0 -> +1, 1 -> -1.
- QPSK: bits (b0, b1) -> ((1 - 2 b0) + j (1 - 2 b1)) / sqrt 2.
- 8PSK: 3 bits, label L at phase position p where L = gray(p): exp(j 2 pi p / 8).
- 16/64-QAM: the first half of each symbol's bits Gray-code the I level, the second half Q.
- M-FSK: log2(M) bits, label at Gray position g -> tone (2 g - M + 1) * deviation cycles/sample,
  phase continuous.
"""

from typing import Any

import numpy as np
from numpy.typing import NDArray

from dsp.synth.waveforms import rrc_taps

Complex = NDArray[np.complex128]

BITS_PER_SYMBOL = {"bpsk": 1, "qpsk": 2, "8psk": 3, "16qam": 4, "64qam": 6}
LINEAR = tuple(BITS_PER_SYMBOL)
# Offset QPSK carries QPSK's symbols with the Q stream a half symbol late (`pulse_shape_offset`);
# it is a linear modulation with its own pulse shaping, so it stays out of LINEAR.
OFFSET = "oqpsk"


def gray(n: NDArray[Any]) -> NDArray[np.int64]:
    """Position -> the Gray label it carries."""
    v = np.asarray(n, dtype=np.int64)
    return v ^ (v >> 1)


def gray_position(label: NDArray[Any]) -> NDArray[np.int64]:
    """Gray label -> its position (the inverse of `gray`), so neighbours differ in one bit."""
    p = np.asarray(label, dtype=np.int64).copy()
    shift = 1
    while shift < 64:
        p ^= p >> shift
        shift <<= 1
    return p


def _indices(bits: NDArray[Any], width: int) -> NDArray[np.int64]:
    if len(bits) % width:
        raise ValueError(f"{len(bits)} bits aren't whole {width}-bit symbols")
    b = np.asarray(bits, dtype=np.int64).reshape(-1, width)
    return b @ (1 << np.arange(width - 1, -1, -1))


def _pam(bits: NDArray[Any], width: int) -> NDArray[np.float64]:
    """Gray-coded PAM levels -(L-1) .. (L-1) for `width` bits per level."""
    levels = 1 << width
    return (2 * gray_position(_indices(bits, width)) - (levels - 1)).astype(np.float64)


def map_bits(bits: NDArray[Any], modulation: str) -> Complex:
    """Symbols with unit average energy for a linear modulation."""
    if modulation == "bpsk":
        return (1 - 2 * np.asarray(bits, dtype=np.float64)).astype(np.complex128)
    if modulation == "qpsk":
        b = np.asarray(bits, dtype=np.float64).reshape(-1, 2)
        return ((1 - 2 * b[:, 0]) + 1j * (1 - 2 * b[:, 1])) / np.sqrt(2)
    if modulation == "8psk":
        return np.exp(2j * np.pi * gray_position(_indices(bits, 3)) / 8)
    if modulation in ("16qam", "64qam"):
        w = BITS_PER_SYMBOL[modulation]
        b = np.asarray(bits).reshape(-1, w)
        i, q = _pam(b[:, : w // 2].ravel(), w // 2), _pam(b[:, w // 2 :].ravel(), w // 2)
        levels = 1 << (w // 2)
        energy = 2 * (levels**2 - 1) / 3
        return (i + 1j * q) / np.sqrt(energy)
    raise ValueError(f"unknown linear modulation {modulation!r}")


def pulse_shape(symbols: Complex, sps: int, shape: str, rolloff: float, span: int = 16) -> Complex:
    """Symbols at `sps` samples each; symbol k's peak sits at sample k * sps (delay removed)."""
    up = np.zeros(len(symbols) * sps, dtype=np.complex128)
    up[::sps] = symbols
    if shape == "rect":
        return np.convolve(up, np.ones(sps))[: len(up)]
    if shape != "rrc":
        raise ValueError(f"unknown pulse shape {shape!r}")
    taps = rrc_taps(sps, rolloff, span) * np.sqrt(sps)
    return np.convolve(up, taps)[span * sps // 2 : span * sps // 2 + len(up)]


def pulse_shape_offset(
    symbols: Complex, sps: int, shape: str, rolloff: float, span: int = 16
) -> Complex:
    """Offset QPSK: the I and Q streams shaped alike, Q delayed by half a symbol (`sps` even), so
    I peaks at k * sps and Q at k * sps + sps / 2."""
    if sps % 2:
        raise ValueError("offset QPSK needs an even number of samples per symbol")
    i = pulse_shape(symbols.real.astype(np.complex128), sps, shape, rolloff, span)
    q = pulse_shape(symbols.imag.astype(np.complex128), sps, shape, rolloff, span)
    return i + 1j * np.concatenate([np.zeros(sps // 2, np.complex128), q[: len(q) - sps // 2]])


def _gaussian_taps(sps: int, bt: float, span_symbols: int = 3) -> NDArray[np.float64]:
    """Gaussian premodulation filter taps (GFSK-style: the same closed form GMSK's premod
    filter uses, bandwidth-time product `bt`), unit sum so a run of one tone keeps its exact
    frequency once the filter has settled - only the transitions between tones are smoothed."""
    n = span_symbols * sps
    t: NDArray[np.float64] = np.arange(-n, n + 1, dtype=np.float64) / sps
    h: NDArray[np.float64] = np.exp(-2 * (np.pi * bt * t) ** 2 / np.log(2))
    return h / np.sum(h)


def fsk(bits: NDArray[Any], order: int, sps: int, deviation: float, bt: float = 0.0) -> Complex:
    """`bt` = 0 (the default) is an abrupt step at each symbol, exact at every sample: what the
    unit tests below check against. `bt` > 0 passes the tone trajectory through a Gaussian
    premodulation filter first, as GFSK does, rounding those steps so the transmitted spectrum
    doesn't splatter between tones (PLAN §5 M2's bench notes); `dsp.synth.chain` is the caller
    that turns this on for the signals it generates.
    """
    width = order.bit_length() - 1
    if 1 << width != order:
        raise ValueError("FSK order must be a power of two")
    g = gray_position(_indices(bits, width))
    frequency = np.repeat((2 * g - order + 1) * deviation, sps).astype(np.float64)
    if bt > 0:
        taps = _gaussian_taps(sps, bt)
        pad = len(taps) // 2
        frequency = np.convolve(np.pad(frequency, pad, mode="edge"), taps, mode="valid")
    return np.exp(2j * np.pi * np.cumsum(frequency))


def audio(rng: np.random.Generator, n: int, bandwidth: float) -> NDArray[np.float64]:
    """Band-limited noise standing in for speech: `bandwidth` in cycles/sample, unit RMS."""
    spectrum = np.fft.rfft(rng.standard_normal(n))
    spectrum[int(bandwidth * n) :] = 0
    x = np.fft.irfft(spectrum, n)
    return x / np.sqrt(np.mean(x**2))


def am(message: NDArray[Any], depth: float) -> Complex:
    return (1 + depth * np.asarray(message) / np.max(np.abs(message))).astype(np.complex128)


def fm(message: NDArray[Any], deviation: float) -> Complex:
    """Frequency modulation with peak deviation `deviation` cycles/sample."""
    m = np.asarray(message) / np.max(np.abs(message))
    return np.exp(2j * np.pi * deviation * np.cumsum(m))


def resample(x: Complex, times: NDArray[np.float64], half_width: int = 16) -> Complex:
    """x evaluated at fractional sample `times` by Kaiser-windowed sinc interpolation.

    `times` must be non-decreasing; its spacing is the output sample interval in input samples
    (> 1 decimates, and the sinc is widened to stay anti-aliased).
    """
    step = float(np.median(np.diff(times))) if len(times) > 1 else 1.0
    cutoff = min(1.0, 1.0 / step)
    out = np.empty(len(times), dtype=np.complex128)
    width = int(np.ceil(half_width / cutoff))
    offsets = np.arange(-width + 1, width + 1)
    window_beta = 8.0
    for start in range(0, len(times), 1 << 14):
        t = times[start : start + (1 << 14)]
        base = np.floor(t).astype(np.int64)
        index = base[:, None] + offsets[None, :]
        frac = t[:, None] - index
        inside = np.clip(1 - (frac / width) ** 2, 0, None)
        kernel = cutoff * np.sinc(cutoff * frac) * np.i0(window_beta * np.sqrt(inside))
        kernel /= np.i0(window_beta)
        valid = (index >= 0) & (index < len(x))
        samples = np.where(valid, x[np.clip(index, 0, len(x) - 1)], 0)
        out[start : start + len(t)] = np.sum(kernel * samples, axis=1)
    return out
