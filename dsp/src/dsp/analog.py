"""Analog AM/FM detection, before digital classification (PLAN §5 M2).

A signal carrying AM has an envelope that varies with its message and a near-constant carrier
frequency; FM is the opposite: a near-constant envelope and a varying instantaneous frequency.
Both properties are tested against the floor AWGN alone would produce at the signal's own
power, from the standard high-SNR Rician approximations for a noisy tone: additive noise of
power N on a carrier of power A^2 gives the envelope coefficient of variation
sqrt(N / 2) / sqrt(A^2 + N), and the instantaneous-frequency standard deviation (cycles/sample)
sqrt(N / A^2) / (2 pi) (two independent phase-noise samples are differenced, hence no extra
factor of 2 beyond the single-sample phase variance N / (2 A^2)).

A signal is AM when its envelope variation clears its floor by MARGIN while its frequency
variation does not; FM the other way round; anything else (including a signal too weak for
either floor to be meaningful) is neither, and is left to the digital chain and open-set
rejection (M4) instead of a forced label.

M-FSK is constant-envelope and frequency-varying too - the same signature as FM - so an FM
candidate is also checked for a Gaussian-like frequency distribution (`FSK_KURTOSIS_GATE`):
FSK's tones give it a well below-Gaussian (negative excess) kurtosis that a continuous message
does not.

Measurements (`measure_analog`): the carrier's offset from the channel centre (the power-weighted
mean frequency, the phase of the lag-one autocorrelation); for AM the RMS modulation depth (RMS of
the message over the carrier amplitude, from the envelope's coefficient of variation less the
noise floor's, in quadrature) and the audio bandwidth (99 % of the message's power above its
noise floor, `occupied_bandwidth`); for FM the RMS frequency deviation (the frequency spread less
the floor's, in quadrature). A peak depth or peak deviation would need the message's crest
factor, which speech and noise do not share, so none is claimed; FM's audio bandwidth is not
measured, since the discriminator's noise rises with frequency and has no flat floor to read it
against.

Limits: MARGIN=2 needs the modulation to clearly dominate the noise floor, which for a modest
index (as commonly used here) needs on the order of 15-20 dB SNR for AM and more for FM, whose
deviation-driven frequency spread is usually smaller relative to its floor than AM's
envelope spread is to its own; below that this correctly abstains rather than guessing. SSB
and Morse CW are not implemented: dsp.synth has no SSB or CW generator to test against, so
nothing here claims to detect them (never claim what isn't tested against ground truth).
"""

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from dsp import _scipy

Complex = NDArray[np.complex128]

MARGIN = 2.0  # the floor must be cleared by at least this factor to call it real modulation
MIN_FLOOR = 1e-9  # a floor collapses to ~0 for pure noise (A^2 -> 0); avoid dividing by it
# M-FSK's instantaneous frequency sits at a few discrete tones, not a continuous message, so its
# excess kurtosis is well below a Gaussian's (0); analog FM's frequency, message-driven, is not.
FSK_KURTOSIS_GATE = -0.75


@dataclass(frozen=True)
class AnalogMetrics:
    envelope_cv: float
    envelope_floor: float
    frequency_std: float  # cycles/sample
    frequency_floor: float
    frequency_kurtosis: float  # excess kurtosis; well below 0 flags discrete tones (M-FSK)
    carrier_power: float  # A^2, estimated
    noise_power: float  # N, estimated


@dataclass(frozen=True)
class AnalogResult:
    kind: Literal["am", "fm"]
    metrics: AnalogMetrics


def analog_metrics(x: Complex, noise_power: float) -> AnalogMetrics:
    """The envelope and frequency statistics `analog_detect` decides from, and the AWGN-only
    floor each is compared against, given the channel's own noise power (from `snr_psd`)."""
    envelope = np.abs(x)
    mean_power = float(np.mean(envelope**2))
    carrier_power = max(mean_power - noise_power, 0.0)
    envelope_floor = math.sqrt(noise_power / 2) / math.sqrt(max(mean_power, MIN_FLOOR))
    frequency_floor = math.sqrt(noise_power / max(carrier_power, MIN_FLOOR)) / (2 * math.pi)
    frequency = np.diff(np.unwrap(np.angle(x))) / (2 * math.pi)
    return AnalogMetrics(
        envelope_cv=float(np.std(envelope) / max(np.mean(envelope), MIN_FLOOR)),
        envelope_floor=envelope_floor,
        frequency_std=float(np.std(frequency)),
        frequency_floor=frequency_floor,
        frequency_kurtosis=_scipy.excess_kurtosis(frequency),
        carrier_power=carrier_power,
        noise_power=noise_power,
    )


@dataclass(frozen=True)
class AnalogMeasurements:
    carrier_offset: float  # cycles/sample from the channel centre
    am_depth_rms: float | None  # RMS message amplitude / carrier amplitude
    fm_deviation_rms: float | None  # RMS of the instantaneous frequency, cycles/sample
    audio_bandwidth: float | None  # AM only, cycles/sample
    message_samples: int


def measure_analog(x: Complex, result: AnalogResult) -> AnalogMeasurements:
    """What an AM or FM signal's carrier and message measure (see the module docstring), from the
    same channel `analog_detect` decided on."""
    m = result.metrics
    lag_one = complex(np.mean(x[1:] * np.conj(x[:-1])))
    offset = math.atan2(lag_one.imag, lag_one.real) / (2 * math.pi)
    if result.kind == "am":
        envelope = np.abs(x)
        cv2 = max((m.envelope_cv**2) - (m.envelope_floor**2), 0.0)
        message = envelope / max(float(np.mean(envelope)), MIN_FLOOR) - 1.0
        bandwidth = _message_bandwidth(message)
        return AnalogMeasurements(offset, math.sqrt(cv2), None, bandwidth, len(x))
    spread2 = max(m.frequency_std**2 - m.frequency_floor**2, 0.0)
    return AnalogMeasurements(offset, None, math.sqrt(spread2), None, len(x))


def _message_bandwidth(message: NDArray[np.float64]) -> float | None:
    """The one-sided bandwidth holding 99 % of a real message's power above its noise floor, or
    None when it is too short to measure."""
    from dsp.estimate.params import occupied_bandwidth
    from dsp.spectrum import welch, welch_dof, welch_freqs

    nfft = 1024
    if len(message) < 4 * nfft:
        return None
    psd = welch(message, nfft)
    freqs = welch_freqs(len(message), nfft, True)
    band = occupied_bandwidth(psd, freqs, dof=welch_dof(len(message), nfft))
    return float(band.high)


def analog_detect(x: Complex, noise_power: float, margin: float = MARGIN) -> AnalogResult | None:
    """AM or FM, from a channel already centred on the carrier; None if neither clears its
    floor, the carrier is too weak (below the noise) for either floor to mean anything, or the
    frequency looks like M-FSK's discrete tones rather than a continuous message."""
    m = analog_metrics(x, noise_power)
    if m.carrier_power <= MIN_FLOOR:
        return None
    is_am = (
        m.envelope_cv > margin * m.envelope_floor and m.frequency_std < margin * m.frequency_floor
    )
    is_fm = (
        m.frequency_std > margin * m.frequency_floor
        and m.envelope_cv < margin * m.envelope_floor
        and m.frequency_kurtosis > FSK_KURTOSIS_GATE
    )
    if is_am and not is_fm:
        return AnalogResult("am", m)
    if is_fm and not is_am:
        return AnalogResult("fm", m)
    return None
