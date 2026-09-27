"""Channel and receiver impairments, each seeded and each recorded in the truth.

Frequencies are in cycles per sample and times in samples. The order applied by the chain is
the physical one: multipath, carrier offset and phase noise, receiver clock drift, IQ imbalance,
AGC, clipping, then additive noise.
"""

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dsp.synth.modulate import resample

Complex = NDArray[np.complex128]


@dataclass(frozen=True)
class Impairments:
    cfo: float = 0.0  # carrier frequency offset, cycles/sample
    phase: float = 0.0  # initial carrier phase, radians
    phase_noise: float = 0.0  # Wiener phase-noise step standard deviation, radians/sample
    iq_gain_db: float = 0.0  # I/Q amplitude imbalance
    iq_phase_deg: float = 0.0  # I/Q quadrature error
    multipath: tuple[tuple[float, float, float], ...] = ()  # (delay samples, gain, phase rad)
    fading_doppler: float = 0.0  # Rayleigh fading on every path, max Doppler cycles/sample
    clock_ppm: float = 0.0  # receiver sample-clock offset
    clock_drift_ppm: float = 0.0  # further change in clock offset across the recording
    agc_db: float = 0.0  # peak-to-peak slow gain variation
    agc_period: float = 0.0  # samples per AGC cycle
    clip: float | None = None  # clip I and Q at this multiple of the signal RMS

    def truth(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: (list(map(list, v)) if k == "multipath" else v) for k, v in d.items()}


def apply(x: Complex, imp: Impairments, rng: np.random.Generator) -> Complex:
    y = x.astype(np.complex128)
    n = np.arange(len(y))
    if imp.multipath:
        y = _multipath(y, imp, rng)
    if imp.cfo or imp.phase or imp.phase_noise:
        walk = np.cumsum(rng.standard_normal(len(y)) * imp.phase_noise)
        y = y * np.exp(1j * (2 * np.pi * imp.cfo * n + imp.phase + walk))
    if imp.clock_ppm or imp.clock_drift_ppm:
        ppm = imp.clock_ppm + imp.clock_drift_ppm * n / max(len(y), 1)
        y = resample(y, np.cumsum(1 + ppm * 1e-6) - 1)
    if imp.iq_gain_db or imp.iq_phase_deg:
        g = 10 ** (imp.iq_gain_db / 20)
        phi = np.deg2rad(imp.iq_phase_deg)
        i, q = y.real, y.imag
        y = i + 1j * g * (q * np.cos(phi) + i * np.sin(phi))
    if imp.agc_db and imp.agc_period:
        y = y * 10 ** (imp.agc_db / 40 * np.sin(2 * np.pi * n / imp.agc_period))
    if imp.clip is not None:
        level = imp.clip * np.sqrt(np.mean(np.abs(y) ** 2) / 2)
        y = np.clip(y.real, -level, level) + 1j * np.clip(y.imag, -level, level)
    return y


def _multipath(x: Complex, imp: Impairments, rng: np.random.Generator) -> Complex:
    out = np.zeros(len(x), dtype=np.complex128)
    times = np.arange(len(x), dtype=np.float64)
    for delay, gain, phase in imp.multipath:
        path = resample(x, times - delay) * gain * np.exp(1j * phase)
        if imp.fading_doppler:
            path = path * _rayleigh(len(x), imp.fading_doppler, rng)
        out += path
    return out


def _rayleigh(n: int, doppler: float, rng: np.random.Generator, paths: int = 16) -> Complex:
    """Sum-of-sinusoids Rayleigh fading with unit mean power (Clarke's model)."""
    t = np.arange(n)
    angles = rng.uniform(0, 2 * np.pi, paths)
    phases = rng.uniform(0, 2 * np.pi, (2, paths))
    f = doppler * np.cos(angles)
    i = np.cos(2 * np.pi * f[None, :] * t[:, None] + phases[0]).sum(axis=1)
    q = np.sin(2 * np.pi * f[None, :] * t[:, None] + phases[1]).sum(axis=1)
    return (i + 1j * q) / np.sqrt(paths)


def awgn(rng: np.random.Generator, n: int, power: float) -> Complex:
    scale = np.sqrt(power / 2)
    return scale * rng.standard_normal(n) + 1j * scale * rng.standard_normal(n)
