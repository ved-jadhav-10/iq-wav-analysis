"""Symbol timing and carrier recovery for linear modulations (PLAN M3).

From a channel centred on a detection (`dsp.channel`) and its estimated symbol rate:
1. resample to SPS samples per symbol (Kaiser-windowed sinc interpolation);
2. RRC matched filter at the estimated roll-off;
3. timing: the Oerder-Meyr square-law estimate per block of symbols, unwrapped across blocks,
   so a small symbol-rate error shows up as a drift and is followed; the matched-filter output
   is interpolated at the recovered symbol instants;
   Offset QPSK (`offset=True`): its |x|² line cancels (I² and Q² peak half a symbol apart), but
   the line of x² does not: its phase puts the real part's peaks at the timing instants and the
   imaginary part is read half a symbol later (`Timing.symbols`) or earlier (`Timing.alternate`):
   which stream leads is the quarter-turn the carrier phase leaves open, so both pairings are
   returned and the search decides; a carrier offset `cfo` (from `dsp.estimate.offset`) is
   removed first, and the carrier phase from the fourth power per block (`_block_phase`);
4. carrier (`correct_carrier`, per PSK order M): the M-th power line gives the residual CFO,
   then the M-th power phase per block, unwrapped, tracks what is left. The M-fold phase
   ambiguity stays: callers try every rotation and let the CRC decide.
"""

import math
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from dsp import _scipy
from dsp.parallel import pmap

Complex = NDArray[np.complex128]
Float = NDArray[np.float64]

SPS = 4  # samples per symbol the matched filter and timing run at
TIMING_BLOCK = 256  # symbols per Oerder-Meyr timing estimate
PHASE_BLOCK = 128  # symbols per carrier-phase estimate
RRC_SPAN = 16  # symbols
INTERPOLATE_CHUNK_ELEMENTS = 1 << 19  # values per matrix in one chunk of `interpolate`


def interpolate(
    x: Complex, times: Float, half_width: int = 16, *, anti_alias: bool = True
) -> Complex:
    """x evaluated at fractional sample `times` by Kaiser-windowed sinc interpolation (the same
    interpolator as `dsp.synth.modulate.resample`); spacing > 1 decimates, with the sinc widened
    to stay anti-aliased unless `anti_alias` is off (sampling at symbol instants, where the
    aliasing is the point and a low-pass would add intersymbol interference)."""
    step = float(np.median(np.diff(times))) if len(times) > 1 else 1.0
    cutoff = min(1.0, 1.0 / step) if anti_alias else 1.0
    out = np.empty(len(times), dtype=np.complex128)
    width = int(np.ceil(half_width / cutoff))
    offsets = np.arange(-width + 1, width + 1)
    window_beta = 8.0
    norm = float(_scipy.i0(np.array(window_beta)))
    # Rows of the kernel matrix are independent, so chunks of them run side by side; a chunk is
    # at most INTERPOLATE_CHUNK_ELEMENTS values per matrix, which bounds each thread's memory.
    rows = int(np.clip(INTERPOLATE_CHUNK_ELEMENTS // len(offsets), 64, 1 << 14))

    def chunk(start: int) -> None:
        t = times[start : start + rows]
        base = np.floor(t).astype(np.int64)
        index = base[:, None] + offsets[None, :]
        frac = t[:, None] - index
        inside = np.clip(1 - (frac / width) ** 2, 0, None)
        kernel = cutoff * np.sinc(cutoff * frac) * _scipy.i0(window_beta * np.sqrt(inside))
        kernel /= norm
        valid = (index >= 0) & (index < len(x))
        samples = np.where(valid, x[np.clip(index, 0, len(x) - 1)], 0)
        out[start : start + len(t)] = np.sum(kernel * samples, axis=1)

    pmap(chunk, range(0, len(times), rows))
    return out


def rrc_taps(sps: int, rolloff: float, span: int = RRC_SPAN) -> Float:
    """Root-raised-cosine pulse over `span` symbols, unit energy."""
    t = np.arange(-span * sps // 2, span * sps // 2 + 1) / sps
    b = rolloff
    h = np.empty_like(t)
    for i, ti in enumerate(t):
        if ti == 0:
            h[i] = 1 + b * (4 / np.pi - 1)
        elif np.isclose(abs(ti), 1 / (4 * b)):
            h[i] = (b / np.sqrt(2)) * (
                (1 + 2 / np.pi) * np.sin(np.pi / (4 * b))
                + (1 - 2 / np.pi) * np.cos(np.pi / (4 * b))
            )
        else:
            h[i] = (np.sin(np.pi * ti * (1 - b)) + 4 * b * ti * np.cos(np.pi * ti * (1 + b))) / (
                np.pi * ti * (1 - (4 * b * ti) ** 2)
            )
    return h / np.sqrt(np.sum(h**2))


@dataclass(frozen=True)
class Timing:
    symbols: Complex  # one complex sample per symbol, unit RMS, carrier not yet corrected
    rate: float  # symbols per channel sample, after the drift correction
    drift: float  # the timing drift followed, in symbols over the whole run
    jitter: float  # RMS scatter of the block timing estimates about their trend, in symbols
    # What the eye diagram is drawn from: the matched-filter output at SPS samples per symbol,
    # and the sample position of each symbol in it (one per entry of `symbols`).
    matched: Complex = field(default_factory=lambda: np.zeros(0, np.complex128), repr=False)
    instants: Float = field(default_factory=lambda: np.zeros(0), repr=False)
    cfo: float = 0.0  # cycles per channel sample removed before timing (offset QPSK only)
    # Offset QPSK only: the same instants with the imaginary part read half a symbol earlier, not
    # later (the pairing when the quarter-turn ambiguity swaps which stream leads).
    alternate: Complex = field(default_factory=lambda: np.zeros(0, np.complex128), repr=False)


def recover_timing(
    x: Complex, rate: float, rolloff: float, *, offset: bool = False, cfo: float = 0.0
) -> Timing:
    """Symbols from channel samples `x` at `rate` symbols per sample (from `symbol_rate`). With
    `offset`, the signal is offset QPSK: `cfo` (cycles per sample) is removed first, timing comes
    from the line of y² and a symbol is the real part at the instant plus j times the imaginary
    part half a symbol later (`symbols`) or earlier (`alternate`)."""
    if offset and cfo:
        x = x * np.exp(-2j * np.pi * cfo * np.arange(len(x)))
    grid = np.arange(0.0, len(x) - 1, 1.0 / (SPS * rate))
    y = interpolate(x, grid)
    y = np.convolve(y, rrc_taps(SPS, rolloff), mode="same")
    blocks = len(y) // (SPS * TIMING_BLOCK)
    if blocks < 2:
        raise ValueError(f"too few symbols for timing recovery ({len(y) // SPS})")
    n = np.arange(blocks * SPS * TIMING_BLOCK)
    if offset:
        y = y * np.exp(-1j * _block_phase(y, blocks))
    energy = y[: len(n)] ** 2 if offset else np.abs(y[: len(n)]) ** 2
    weighted = (energy * np.exp(-2j * np.pi * n / SPS)).reshape(blocks, -1)
    tau = np.unwrap(-np.angle(weighted.sum(axis=1))) / (2 * np.pi)  # symbols, per block
    centres = (np.arange(blocks) + 0.5) * TIMING_BLOCK
    trend = np.polyfit(centres, tau, 1)
    jitter = float(np.std(tau - np.polyval(trend, centres)))
    count = len(y) // SPS - 1
    k = np.arange(count, dtype=np.float64)
    instants = SPS * (k + np.interp(k, centres, tau))
    half = SPS / 2 if offset else 0.0
    keep = (instants - half >= 0) & (instants + half <= len(y) - 1)
    at = instants[keep]
    alternate = np.zeros(0, np.complex128)
    if offset:
        re = interpolate(y.real.astype(np.complex128), at, anti_alias=False).real
        im = y.imag.astype(np.complex128)
        symbols = re + 1j * interpolate(im, at + half, anti_alias=False).real
        alternate = re + 1j * interpolate(im, at - half, anti_alias=False).real
        alternate = alternate / math.sqrt(float(np.mean(np.abs(alternate) ** 2)))
    else:
        symbols = interpolate(y, at, anti_alias=False)
    symbols = symbols / math.sqrt(float(np.mean(np.abs(symbols) ** 2)))
    slope = float(trend[0])  # symbols of timing drift per symbol
    return Timing(
        symbols, rate * (1 + slope), slope * count, jitter, y, at, cfo, alternate=alternate
    )


def _block_phase(y: Complex, blocks: int) -> Float:
    """The carrier phase at every sample of `y`, modulo a quarter turn, from the fourth power of
    each timing block. The line of y² that gives offset QPSK its timing has the phase 2 phi - 2 pi
    tau, so it needs the carrier phase first; the fourth power does not depend on timing (its time
    average is -|c| e^(4 j phi), the minus sign being the shaped binary I and Q streams' negative
    excess kurtosis) and leaves only the quarter-turn ambiguity, which swaps which stream is I
    and shifts the bit pairing by one, which the callers' rotation and alignment search covers."""
    size = SPS * TIMING_BLOCK
    power = (-(y[: blocks * size] ** 4)).reshape(blocks, size).sum(axis=1)
    phase = np.unwrap(np.angle(power)) / 4
    centres = (np.arange(blocks) + 0.5) * size
    return np.interp(np.arange(len(y)), centres, phase)


@dataclass(frozen=True)
class Carrier:
    symbols: Complex  # carrier-corrected, the M-fold ambiguity left unresolved
    order: int
    cfo: float  # cycles per symbol
    cfo_uncertainty: float  # cycles per symbol
    phase_spread: float  # RMS of the block phase estimates about the CFO ramp, radians


def correct_carrier(symbols: Complex, order: int) -> Carrier:
    """Remove the carrier offset and phase with the M-th power (M = `order`, the PSK order).

    Ideal M-PSK points put their M-th power on +1 for BPSK (M=2) and on -1 for QPSK at
    +-45 degrees (M=4), so after correction BPSK sits on the real axis and QPSK on the diagonals.
    """
    target = -1.0 if order == 4 else 1.0  # 8PSK's points also sit on +1 at the 8th power
    z = target * symbols**order
    nfft = 1 << max(12, math.ceil(math.log2(len(z))) + 2)
    spectrum = np.abs(np.fft.fft(z, nfft))
    k = int(np.argmax(spectrum))
    if 0 < k < nfft - 1:  # parabolic interpolation on the log magnitude
        a, b, c = np.log(spectrum[k - 1 : k + 2] + 1e-300)
        k_frac = k + 0.5 * (a - c) / (a - 2 * b + c)
    else:
        k_frac = float(k)
    f = ((k_frac / nfft + 0.5) % 1.0) - 0.5
    cfo = f / order
    n = np.arange(len(symbols))
    derotated = symbols * np.exp(-2j * np.pi * cfo * n)
    z = target * derotated**order
    blocks = max(1, len(z) // PHASE_BLOCK)
    phases = np.unwrap(np.angle(z[: blocks * PHASE_BLOCK].reshape(blocks, -1).sum(axis=1)))
    centres = (np.arange(blocks) + 0.5) * PHASE_BLOCK
    theta = np.interp(n, centres, phases) / order
    corrected = derotated * np.exp(-1j * theta)
    trend = np.polyfit(centres, phases / order, 1) if blocks > 1 else np.zeros(2)
    spread = float(np.std(phases / order - np.polyval(trend, centres))) if blocks > 1 else 0.0
    # The phase track's mean slope is residual CFO the FFT line missed; the line's own
    # resolution (one bin of the unpadded M-th power spectrum, over M) bounds the uncertainty.
    residual = float(trend[0]) / (2 * math.pi)
    return Carrier(corrected, order, cfo + residual, 1.0 / (order * len(z)), spread)
