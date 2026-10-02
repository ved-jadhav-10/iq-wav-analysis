"""Parameter estimation on a channelised signal (PLAN §5 M2): SNR, occupied bandwidth, roll-off,
symbol rate, carrier offset and cumulants.

Every estimator takes plain baseband samples (dsp.channel.channelise output) and returns a
small result type with its own uncertainty and evidence; nothing here builds a `Parameter` -
that is the stage's job, once a stage exists to run these on a detection. Frequencies are in
cycles per sample of the *channelised* signal unless stated otherwise.
"""

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dsp import _scipy
from dsp.estimate.lines import Line, find_lines
from dsp.spectrum import welch, welch_dof, welch_freqs

Complex = NDArray[np.complex128]
Float = NDArray[np.float64]

ENERGY_FRACTION = 0.99  # occupied bandwidth captures this share of the in-band energy
PEAK_TO_MEDIAN_GATE = 4.0  # |x| this peaky is not constant-modulus: M-th power CFO is skipped
# Only these get an M-th power CFO line: QAM is gated out (its modulus isn't constant, so the
# naive M-th power breaks, STANDARDS §6), and 8-PSK's 8th power is excluded because on a
# pulse-shaped (not symbol-rate-sampled) waveform its line is too weak to find reliably, the
# amplitude also varying with ISI, not just the phase.
PSK_ORDERS = {"bpsk": 2, "qpsk": 4}


@dataclass(frozen=True)
class OccupiedBandwidth:
    low: float  # cycles/sample
    high: float
    fraction: float  # energy fraction actually captured (== ENERGY_FRACTION unless clipped)

    @property
    def bandwidth(self) -> float:
        return self.high - self.low


FLOOR_RANK = 0.2  # percentile of the PSD taken as the noise floor, low enough to stay off-signal


def occupied_bandwidth(
    psd: Float,
    freqs: Float,
    fraction: float = ENERGY_FRACTION,
    dof: float = 1.0,
    noise_floor: float | None = None,
) -> OccupiedBandwidth:
    """The narrowest band, centred on the power centroid, holding `fraction` of the energy
    above the noise floor. A flat noise floor otherwise never runs out of energy to add, since
    it is spread over the whole channel, so it is subtracted first: a low percentile of the PSD
    stays off the signal's bins as long as they are under FLOOR_RANK of the band (channelisation
    leaves them well under that), but that percentile is biased low relative to the mean of the
    noise-only bins' own right-skewed distribution unless corrected by `dof` (from `welch_dof`),
    the averaging behind the PSD - the same correction `dsp.detect.noise_floor` uses. Passing
    the default `dof=1.0` skips the correction, which understates the floor and so overstates
    the bandwidth; pass the PSD's real `dof` whenever it's known.
    """
    if noise_floor is not None:
        floor = noise_floor
    else:
        percentile = float(np.percentile(psd, 100 * FLOOR_RANK))
        floor = percentile / _scipy.gamma_ppf(FLOOR_RANK, dof)
    above = np.clip(psd - floor, 0.0, None)
    centroid = float(np.sum(freqs * above) / np.sum(above)) if np.sum(above) > 0 else 0.0
    order = np.argsort(np.abs(freqs - centroid))
    cumulative = np.cumsum(above[order])
    target = float(fraction * cumulative[-1])
    k = int(np.searchsorted(cumulative, target)) + 1
    k = min(k, len(order))
    band = freqs[order[:k]]
    got = float(cumulative[min(k, len(order)) - 1] / cumulative[-1]) if cumulative[-1] > 0 else 0.0
    return OccupiedBandwidth(float(band.min()), float(band.max()), got)


@dataclass(frozen=True)
class SnrEstimate:
    snr_db: float
    method: str
    signal_power: float  # the signal's total power, over the noise floor
    noise_density: float  # per unit normalised frequency
    bandwidth: float = 0.0  # the signal's noise-equivalent bandwidth, cycles/sample


SNR_BAND = 0.4  # the |frequency| the SNR estimate reads: a channelised signal is flat out to here
SNR_FLOOR_RANK = 0.4  # percentile of the in-band PSD bins taken as the noise floor
SNR_MIN_FLOOR_SHARE = 0.4  # of the in-band bins that must be left as noise after the signal
SNR_MIN_SIGNIFICANCE = 6.0  # the excess power over its own scatter (noise alone: about 1)


def _refined_floor(p: Float, floor: float, dof: float) -> float:
    """The noise floor as the mean of the bins that sit off the signal. The percentile that
    starts the estimate is pulled up by the signal's bins (at 0 dB they are a fifth of the band,
    above the median of the rest), so the bins whose smoothed level stands above the floor are
    dropped, with a margin of their own width, and the rest averaged. Raises when less than
    `SNR_MIN_FLOOR_SHARE` of the bins are left: no floor can be told from a signal that wide."""
    m = max(8, len(p) // 64)
    smooth = np.convolve(p, np.ones(m) / m, mode="same")
    above = smooth > floor * (1 + 3.0 / math.sqrt(dof * m))
    grown = np.convolve(above.astype(float), np.ones(2 * m + 1), mode="same") > 0
    kept = p[~grown]
    if len(kept) < SNR_MIN_FLOOR_SHARE * len(p):
        raise ValueError("the signal fills too much of the band to find a noise floor beside it")
    return float(kept.mean())


def snr_psd(x: NDArray[Any], nfft: int = 1024) -> SnrEstimate:
    """SNR from the PSD's moments: the signal's power over the noise power in its own
    noise-equivalent bandwidth.

    With the noise density N0 taken from a low percentile of the PSD (corrected for the
    averaging behind it, `welch_dof`), the signal power is S = sum(PSD - N0) and its
    noise-equivalent bandwidth B = S^2 / sum((PSD - N0)^2), less the part of that second sum the
    PSD's own scatter adds (a bin of mean m scatters by m / sqrt(dof)). The SNR is S / (N0 B).
    Unlike a threshold-defined occupied band, no step depends on where the signal ends, so it
    holds down to 0 dB: on RRC-shaped linear signals it reads within 0.6 dB of the in-symbol-rate
    SNR from 0 to 30 dB (`bench/results/bench-v0-detect.md`), and B is about R / (1 - rolloff / 4)
    for symbol rate R, so it sits roughly 0.4 dB below Es/N0 for a roll-off of 0.35.

    Limits: the signal must leave at least SNR_MIN_FLOOR_SHARE of the |f| < SNR_BAND bins as noise
    (channelisation leaves it about five sixths), else ValueError, and must stand
    SNR_MIN_SIGNIFICANCE times above the scatter of a noise-only sum, else ValueError. It must be
    one continuous lobe whose spectrum falls to the noise: M-FSK's separated tones give a B of
    their own, which is not the symbol rate's, so the bench does not score it, and a rectangular
    pulse's sidelobes sit above the noise, which the floor reads as noise (Es/N0 reads up to
    about 1.3 dB low at moderate SNR, and the sidelobes fill the band at high SNR, where it
    raises). A real (one-sided) recording keeps one of the two mirrored lobes. One of the three
    estimators PLAN §5 M2 calls for (M2M4 on the recovered symbols is `snr_m2m4`; eigenvalue/MDL
    is not built).
    """
    real = not np.iscomplexobj(x)
    psd = welch(x, nfft)
    freqs = welch_freqs(len(x), nfft, real)
    dof = welch_dof(len(x), nfft)
    inside = np.abs(freqs) <= SNR_BAND
    if int(inside.sum()) < 16:
        raise ValueError("too few bins inside the passband to estimate a noise floor")
    p = psd[inside]
    width = float(freqs[1] - freqs[0]) if len(freqs) > 1 else 1.0
    floor = float(np.percentile(p, 100 * SNR_FLOOR_RANK)) / _scipy.gamma_ppf(SNR_FLOOR_RANK, dof)
    floor = _refined_floor(p, floor, dof)
    excess = p - floor
    power = float(excess.sum()) * width
    spread = float(np.sum(excess**2 - p**2 / dof)) * width
    # The excess of noise alone sums to zero with a scatter of floor / sqrt(dof) per bin.
    scatter = floor * math.sqrt(len(p) / dof) * width
    if power <= SNR_MIN_SIGNIFICANCE * scatter or spread <= 0:
        raise ValueError("no signal stands above the noise floor")
    bandwidth = power * power / spread
    snr = power / (floor * bandwidth)
    return SnrEstimate(
        10 * math.log10(snr),
        "PSD moments: signal power over the noise floor in its noise-equivalent bandwidth",
        power,
        floor,
        bandwidth,
    )


def snr_m2m4(symbols: Complex, kurtosis: float = 1.0) -> float | None:
    """Es/N0 in dB from the second and fourth moments of recovered symbols (M2M4, Matzner 1993).

    With M2 = E|y|^2 and M4 = E|y|^4 of signal s in circular Gaussian noise w, and the signal's
    kurtosis ka = E|s|^4 / E|s|^2^2 (the noise's is 2): M2 = S + N and M4 = (ka - 2) S^2 + 2 M2^2,
    so S = sqrt((2 M2^2 - M4) / (2 - ka)) and N = M2 - S.

    `kurtosis` is the constellation's: 1 for BPSK/QPSK/8PSK, 1.32 for 16QAM, 1.381 for 64QAM.
    Needs symbol-spaced samples (a residual carrier does not matter, the moments are
    phase-blind); biased by intersymbol interference and timing error, and its scatter grows
    quickly toward 0 dB. Returns None when the moments admit no solution (noise alone, or fewer
    than 256 symbols)."""
    y = np.asarray(symbols, np.complex128)
    if len(y) < 256 or kurtosis >= 2.0:
        return None
    m2 = float(np.mean(np.abs(y) ** 2))
    m4 = float(np.mean(np.abs(y) ** 4))
    square = (2 * m2 * m2 - m4) / (2 - kurtosis)
    if square <= 0:
        return None
    s = math.sqrt(square)
    n = m2 - s
    if n <= 0:
        return None
    return 10 * math.log10(s / n)


@dataclass(frozen=True)
class Cumulants:
    c20: complex  # E[x^2]
    c40: complex  # E[x^4] - 3 E[x^2]^2
    c42: float  # E[|x|^4] - 2 E[|x|^2]^2 - |E[x^2]|^2


def cumulants(x: Complex) -> Cumulants:
    """Second- and fourth-order cumulants, zero mean assumed (a carrier offset biases C20/C40;
    remove it first if it matters)."""
    m2 = complex(np.mean(x**2))
    m21 = float(np.mean(np.abs(x) ** 2))
    m4 = complex(np.mean(x**4))
    m22 = float(np.mean(np.abs(x) ** 4))
    return Cumulants(m2, m4 - 3 * m2**2, m22 - 2 * m21**2 - abs(m2) ** 2)


@dataclass(frozen=True)
class SymbolRate:
    normalised_rate: float  # cycles per channelised sample
    uncertainty: float
    ratio: float  # the line's strength over the local spectrum level


def symbol_rate(x: Complex, low: float = 0.01, high: float = 0.5) -> SymbolRate | None:
    """The symbol rate as a line in the spectrum of |x|^2: pulse shaping makes |x|^2 periodic
    at the symbol rate, for a linear modulation. None if no line is significant.

    Constant-envelope signals (FSK, and PSK with a rectangular pulse) have no |x|^2 line;
    use `fsk_symbol_rate` for FSK.
    """
    envelope = np.abs(x) ** 2
    search = find_lines(envelope.astype(np.complex128), low, high)
    line = search.strongest
    if line is None:
        return None
    return SymbolRate(line.frequency, line.uncertainty, line.ratio)


def fsk_symbol_rate(x: Complex, low: float = 0.01, high: float = 0.5) -> SymbolRate | None:
    """The symbol rate of an FSK signal, from the tone-transition rate: a transition can only
    fall on a symbol boundary, so the edge energy |diff|^2 is a Dirac-comb-like process with
    harmonics at every multiple of the symbol rate, not necessarily the fundamental strongest
    (some transitions land on the same tone and contribute no edge, thinning the comb rather
    than removing a particular harmonic). The lowest significant line is taken as the rate."""
    phase = np.unwrap(np.angle(x))
    frequency = np.diff(phase) / (2 * np.pi)
    edges = np.abs(np.diff(frequency)) ** 2
    search = find_lines(edges.astype(np.complex128), low, high)
    if not search.lines:
        return None
    line = min(search.lines, key=lambda ln: ln.frequency)
    return SymbolRate(line.frequency, line.uncertainty, line.ratio)


# Averaging lengths, in samples, of the multi-scale discriminator. A scale L is only trusted for
# fundamentals of at least SCALE_MIN_PERIOD * L samples (a symbol several scales long); the lines
# of a scale are found over the whole band, so that a fundamental's harmonics are not cut off.
DISCRIMINATOR_SCALES = (1, 2, 4, 8)
SCALE_MIN_PERIOD = 3
HARMONICS = 4  # the comb a candidate is scored on: its lines at f, 2f, 3f and 4f
HARMONIC_TOLERANCE = 0.002  # relative, for "the nearest line is at k times f"
MAX_EDGE_LINES = 24


def _edge_energy(x: Complex, scale: int) -> Float | None:
    """The tone-transition energy at one discriminator scale: the phase advance over `scale`
    samples (a frequency averaged over them, which takes the noise down by about `scale` in
    amplitude where the per-sample discriminator drowns at high oversampling), and the energy of
    its change from one window to the next."""
    if len(x) <= 2 * scale + 16:
        return None
    advance = x[scale:] * np.conj(x[:-scale])
    frequency = np.angle(advance) / (2 * np.pi * scale)
    return np.abs(frequency[scale:] - frequency[:-scale]) ** 2


def _comb_candidates(lines: list[Line], scale: int) -> list[tuple[float, Line]]:
    """(comb strength, line) for each line of a scale that could be a symbol rate: long enough for
    the scale, and with at least one more of its first HARMONICS multiples among the lines. The
    strength is the summed line ratios at those multiples: a transition comb has them all, so its
    fundamental outscores its own harmonics and a stray line."""
    out: list[tuple[float, Line]] = []
    for line in lines:
        if line.frequency > 1.0 / (SCALE_MIN_PERIOD * scale):
            continue
        strength, found = line.ratio, 1  # the line itself is the first harmonic
        for k in range(2, HARMONICS + 1):
            target = k * line.frequency
            nearest = min(lines, key=lambda other: abs(other.frequency - target))
            if abs(nearest.frequency - target) <= HARMONIC_TOLERANCE * target:
                strength += nearest.ratio
                found += 1
        if found >= 2:
            out.append((strength, line))
    return out


def fsk_symbol_rates(
    x: Complex, low: float = 0.01, high: float = 0.5, count: int = 3
) -> list[SymbolRate]:
    """Up to `count` candidate FSK symbol rates for a search to settle, strongest transition comb
    first.

    The edge energy is taken at several discriminator scales (`DISCRIMINATOR_SCALES`): the
    per-sample discriminator's noise grows with the oversampling, so above about 8 samples per
    symbol at moderate SNR it shows no line at all, where a frequency averaged over a few samples
    still does. A candidate is a line with harmonics (`_comb_candidates`); comb strength, not
    frequency, orders them, since a structured payload (a 7-bit character period, a frame period)
    has combs of its own and the lowest line is then not the symbol rate. Only when no scale has
    a candidate, as on a signal with too few transitions for a comb, are the per-sample scale's
    lines used as they are, lowest first, as before."""
    per_sample = list(find_lines(_per_sample_edges(x).astype(np.complex128), low, high).lines)
    scored: list[tuple[float, Line]] = []
    for scale in DISCRIMINATOR_SCALES:
        if scale == 1:
            lines = list(
                find_lines(
                    _per_sample_edges(x).astype(np.complex128),
                    low,
                    high,
                    max_lines=MAX_EDGE_LINES,
                ).lines
            )
        else:
            energy = _edge_energy(x, scale)
            lines = (
                []
                if energy is None
                else list(
                    find_lines(
                        energy.astype(np.complex128), low, high, max_lines=MAX_EDGE_LINES
                    ).lines
                )
            )
        scored += _comb_candidates(lines, scale)
    if scored:
        scored.sort(key=lambda item: -item[0])
        ordered = [line for _, line in scored]
    else:
        by_frequency = sorted(per_sample, key=lambda ln: ln.frequency)
        ordered = [*by_frequency[:1], *per_sample[:1], *by_frequency[1:]]
    out: list[SymbolRate] = []
    for line in ordered:
        if all(abs(line.frequency - r.normalised_rate) > 1e-3 * line.frequency for r in out):
            out.append(SymbolRate(line.frequency, line.uncertainty, line.ratio))
    return out[:count]


def _per_sample_edges(x: Complex) -> Float:
    phase = np.unwrap(np.angle(x))
    frequency = np.diff(phase) / (2 * np.pi)
    return np.abs(np.diff(frequency)) ** 2


@dataclass(frozen=True)
class CarrierOffset:
    cfo: float  # cycles/sample, at the channel's own centre
    uncertainty: float
    order: int  # the M-th power used
    ratio: float


def carrier_offset(x: Complex, modulation: str) -> CarrierOffset | None:
    """CFO from an M-th power line, M matching the PSK order; None if the modulation is QAM
    (gated: naive M-th power breaks on QAM's non-constant modulus, STANDARDS §6), isn't a
    supported PSK order (see `PSK_ORDERS`), or the signal isn't peaky enough for M-th power."""
    if modulation not in PSK_ORDERS:
        return None
    order = PSK_ORDERS[modulation]
    envelope = np.abs(x)
    peak_to_median = float(np.max(envelope) / np.median(envelope)) if len(envelope) else 0.0
    if peak_to_median > PEAK_TO_MEDIAN_GATE:
        return None
    powered = x.astype(np.complex128) ** order
    span = 0.5 / order
    search = find_lines(powered, -span, span)
    line = search.strongest
    if line is None:
        return None
    return CarrierOffset(line.frequency / order, line.uncertainty / order, order, line.ratio)


ROLLOFF_CANDIDATES: tuple[float, ...] = (0.15, 0.2, 0.25, 0.3, 0.35, 0.5, 1.0)
DB_FLOOR_LINEAR = 10 ** (-30 / 10)  # roll-off fit: clip both curves at -30 dB before comparing


def rolloff_fit(
    psd: Float,
    freqs: Float,
    rate: float,
    centre: float = 0.0,
    candidates: tuple[float, ...] = ROLLOFF_CANDIDATES,
) -> float:
    """The RRC roll-off, snapped to a standard value, whose ideal spectral shape least-squares
    fits the measured PSD out to 1.2x the widest candidate's edge, given the symbol `rate`
    (from `symbol_rate`) and the channel `centre` (0.0 once the channel is centred on it)."""
    half = 1.2 * rate * (1 + candidates[-1]) / 2
    band = np.abs(freqs - centre) <= half
    p = psd[band]
    f = np.abs(freqs[band] - centre)
    if len(p) < 4 or float(np.max(p)) <= 0:
        return candidates[0]
    # A real filter's stopband, and the estimate's own spectral leakage, sit at a small but
    # non-zero floor; subtracted first, so it isn't mistaken for a wider roll-off's skirt.
    p = np.clip(p - float(np.percentile(p, 5)), 0.0, None)
    if float(np.max(p)) <= 0:
        return candidates[0]
    p = p / np.max(p)
    # Fit in dB: the flat top is noisy but near 0 dB for every candidate, so a linear-power fit
    # is dominated by that noise; dB compresses it and weights the roll-off shape instead.
    p_db = 10 * np.log10(np.maximum(p, DB_FLOOR_LINEAR))
    best_beta, best_error = candidates[0], math.inf
    for beta in candidates:
        shape = _rrc_psd_shape(f, rate, beta)
        shape_db = 10 * np.log10(np.maximum(shape, DB_FLOOR_LINEAR))
        error = float(np.mean((p_db - shape_db) ** 2))
        if error < best_error:
            best_beta, best_error = beta, error
    return best_beta


def _rrc_psd_shape(f: Float, rs: float, beta: float) -> Float:
    """Ideal RRC power spectrum (amplitude, not squared root): 1 in the flat band, a raised
    cosine roll-off, 0 beyond, normalised to 1 at f = 0."""
    if beta <= 0:
        return (f <= rs / 2).astype(np.float64)
    flat = rs * (1 - beta) / 2
    edge = rs * (1 + beta) / 2
    out = np.where(f <= flat, 1.0, 0.0)
    roll = (f > flat) & (f <= edge)
    out = np.where(roll, 0.5 * (1 + np.cos(np.pi / (beta * rs) * (f - flat))), out)
    return np.asarray(out, np.float64)
