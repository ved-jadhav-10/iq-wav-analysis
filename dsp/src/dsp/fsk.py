"""Non-coherent 2/4/8-FSK demodulation to soft bits (PLAN M3).

1. The frequency discriminator: the phase step between successive samples, in cycles/sample.
2. Resampled to SPS samples per symbol at the rate from `fsk_symbol_rates`.
3. Timing from the transitions: a tone change can only happen on a symbol boundary, so the
   squared difference of the frequency is periodic at the symbol rate; its phase per block
   (Oerder-Meyr on |diff|² instead of |y|²), unwrapped, gives the boundaries.
4. Each symbol's value is the frequency averaged over its interior (the middle INTERIOR
   fraction), away from the transitions. For 2-FSK the decision threshold is the median, which
   also removes any residual carrier offset for balanced data. For more tones, the number of
   tones (2, 4 or 8) is the one whose equally spaced, equally likely levels fit the symbol
   values best (`fit_levels`), and each symbol is scored by its energy at every tone.

Mapping matches `dsp.synth.modulate.fsk`: the tone at position p (lowest first) carries the Gray
label p ^ (p >> 1), so bit 0 is on the lower tone of a 2-FSK signal. An inverted spectrum (I/Q
swapped) mirrors the tones: for 2-FSK that inverts every bit, which the framing search's
inverted-sync check covers; for more tones it flips only each label's first bit
(`mirror_first_bit`), which is a hypothesis of its own.
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
ORDERS = (2, 4, 8)  # numbers of tones tried


@dataclass(frozen=True)
class FskSymbols:
    values: Float  # per-symbol energy balance between the outer tones, cycles/channel sample
    llr: Float  # positive means bit 0; log2(order) per symbol, first bit first
    shift: float  # tone spacing, cycles/channel sample
    centre: float  # the centre of the tones (residual carrier offset), cycles/channel sample
    jitter: float  # RMS scatter of the block timing estimates, symbols
    order: int = 2  # number of tones
    # Log-likelihood of the symbol values under each order's equal-spacing model (a constant
    # common to all orders left out), so a report can say how much better the chosen order fits.
    fits: tuple[tuple[int, float], ...] = ()


def fit_levels(values: Float, order: int, rounds: int = 20) -> tuple[float, float, float]:
    """The equally spaced levels (centre, spacing) that best explain `values`, and the residual
    variance: least squares by alternating nearest-level assignment and a straight-line refit."""
    lo, hi = np.percentile(values, [5, 95])
    centre = float(np.median(values))
    spacing = max(float(hi - lo) / max(order - 1, 1), 1e-12)
    half = (order - 1) / 2

    def assign(centre: float, spacing: float) -> NDArray[np.float64]:
        nearest = np.rint((values - centre) / spacing + half)
        return np.clip(nearest, 0, order - 1) - half

    for _ in range(rounds):
        position = assign(centre, spacing)
        if np.ptp(position) == 0:
            break
        slope, intercept = np.polyfit(position, values, 1)
        if slope <= 0:
            break
        spacing, centre = float(slope), float(intercept)
    residual = values - (centre + spacing * assign(centre, spacing))
    return centre, spacing, float(np.mean(residual**2))


def mirror_first_bit(llr: Float, order: int) -> Float:
    """The LLRs of a spectrum-mirrored signal: mirroring tone p to M-1-p flips only the Gray
    label's first bit (`order` 2 is every bit)."""
    width = order.bit_length() - 1
    out = np.array(llr, np.float64, copy=True)
    out[::width] *= -1
    return out


def demodulate(x: Complex, rate: float, order: int | None = None) -> FskSymbols:
    """FSK symbols from channel samples `x` at `rate` symbols per sample. `order` is the number
    of tones; left out, the order (2, 4 or 8) that fits the symbol values best is used."""
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

    # Each symbol's interior, away from the transitions.
    count = len(y) // SPS - 2
    k = np.arange(count, dtype=np.float64)
    starts = SPS * (k + np.interp(k, centres, boundary)) + SPS * (1 - INTERIOR) / 2
    width = max(2, round(SPS * INTERIOR))
    first = np.floor(starts).astype(np.int64)
    ok = (first >= 0) & (first + width < len(y))
    index = first[ok][:, None] + np.arange(width)[None, :]
    segment = y[index]
    means = f[np.minimum(index, len(f) - 1)].mean(axis=1)

    fits = tuple((m, _log_likelihood(means, m)) for m in ORDERS if means.size > 8 * m)
    if order is None:
        order = max(fits, key=lambda item: item[1])[0] if fits else 2
    if order not in ORDERS:
        raise ValueError(f"FSK order {order} is not one of {ORDERS}")
    tones: Float
    if order == 2:
        # Tones from the discriminator's two clusters (per-sample, so noisy, but only their
        # medians are used).
        centre = float(np.median(f))
        upper, lower = f[f > centre], f[f <= centre]
        tones = np.array([float(np.median(lower)), float(np.median(upper))])
        shift = float(tones[1] - tones[0])
    else:
        centre, shift, _ = fit_levels(means, order)
        tones = np.asarray(centre + shift * (np.arange(order) - (order - 1) / 2), np.float64)

    # Non-coherent detection: each symbol's energy at each tone, over its interior.
    tone_list: list[float] = [float(t) for t in tones]
    energies = np.stack(
        [
            np.abs(np.sum(segment * np.exp(-2j * np.pi * tone * index), axis=1)) ** 2
            for tone in tone_list
        ],
        axis=1,
    )
    quiet = np.ones(energies.shape, dtype=bool)
    quiet[np.arange(len(energies)), np.argmax(energies, axis=1)] = False
    noise = float(np.median(energies[quiet])) or 1e-12  # the tones the symbol is not on
    llr = _label_llr(energies, order) / noise
    values = (
        (energies[:, -1] - energies[:, 0]) / np.maximum(energies.sum(axis=1), 1e-12) * shift / 2
    )
    scale = SPS * rate  # cycles per resampled sample -> cycles per channel sample
    return FskSymbols(
        values, np.asarray(llr, np.float64), shift * scale, centre * scale, jitter, order, fits
    )


def _log_likelihood(means: Float, order: int) -> float:
    """Log-likelihood (up to a constant common to all orders) of `means` under `order` equally
    likely, equally spaced levels with one Gaussian variance."""
    variance = max(fit_levels(means, order)[2], 1e-18)
    return -0.5 * means.size * math.log(variance) - means.size * math.log(order)


def _label_llr(energies: Float, order: int) -> Float:
    """Max-log bit LLRs (before noise scaling) from each symbol's tone energies: the tone at
    position p carries the Gray label p ^ (p >> 1), first bit first; positive means bit 0."""
    width = order.bit_length() - 1
    labels = np.arange(order) ^ (np.arange(order) >> 1)
    out = np.empty((len(energies), width))
    for j in range(width):
        bit = (labels >> (width - 1 - j)) & 1
        out[:, j] = energies[:, bit == 0].max(axis=1) - energies[:, bit == 1].max(axis=1)
    return out.ravel()


def _peak(profile: Float) -> float:
    """The circular argmax of a folded profile, refined by a parabola through its neighbours."""
    k = int(np.argmax(profile))
    left, mid, right = profile[k - 1], profile[k], profile[(k + 1) % len(profile)]
    denom = left - 2 * mid + right
    return k + (0.5 * (left - right) / denom if denom < 0 else 0.0)
