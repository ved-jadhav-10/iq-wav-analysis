"""Channelisation: mixing and decimating a detection's band, checked against an exact tone."""

from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from dsp.channel import channelise, decimation_for
from dsp.detect import Detection


class MemorySource:
    def __init__(self, x: NDArray[Any]) -> None:
        self.x = x
        self.num_samples = len(x)

    def read(self, start: int, count: int) -> NDArray[Any]:
        return self.x[start : start + count]


def test_decimation_narrows_by_roughly_the_oversample_factor() -> None:
    d = decimation_for(0.01)
    assert d >= 1
    assert d * 0.01 * 1.5 <= 1.0  # the decimated Nyquist band still holds the margin-widened band


def test_a_tone_survives_channelising_at_the_right_phase_and_frequency() -> None:
    n = 1 << 20
    idx = np.arange(n)
    tone_freq, other_freq = 0.2013, 0.35
    x = np.exp(2j * np.pi * tone_freq * idx) + 0.5 * np.exp(2j * np.pi * other_freq * idx)
    detection = Detection(100_000, 900_000, 0.199, 0.203, 4096, 20.0, 50.0, 10)
    channel = channelise(MemorySource(x.astype(np.complex128)), detection)
    assert channel.decimation > 1
    m = np.arange(len(channel.samples)) * channel.decimation + channel.start
    expected = np.exp(2j * np.pi * (tone_freq - detection.centre) * m)
    # the interfering tone at 0.35 is well outside the channel's passband and is filtered out
    np.testing.assert_allclose(channel.samples[10:-10], expected[10:-10], atol=1e-4)


def test_white_noise_keeps_its_density_after_decimation() -> None:
    rng = np.random.default_rng(0)
    n = 1 << 20
    power = 1.0
    w = np.sqrt(power / 2) * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    detection = Detection(0, n, -0.01, 0.01, 4096, 0.0, 0.0, 1)
    channel = channelise(MemorySource(w), detection)
    # density in = power (over the full band); density out * decimation should match it
    density_out = float(np.var(channel.samples)) * channel.decimation
    assert density_out == pytest.approx(power, rel=0.2)


def test_a_real_sources_mirror_image_is_removed_even_without_decimation() -> None:
    """A real recording's negative-frequency mirror must not leak into the channel, whether or
    not the detected band is wide enough to need decimation (d == 1)."""
    n = 1 << 16
    idx = np.arange(n)
    carrier_freq = 0.35  # wide enough relative to Nyquist that decimation_for gives d == 1
    x = np.cos(2 * np.pi * carrier_freq * idx)
    detection = Detection(0, n, 0.3, 0.4, 4096, 20.0, 50.0, 10)
    channel = channelise(MemorySource(x.astype(np.float64)), detection)
    assert channel.decimation == 1
    spectrum = np.abs(np.fft.fftshift(np.fft.fft(channel.samples)))
    freqs = np.fft.fftshift(np.fft.fftfreq(len(channel.samples)))
    peak_freq = freqs[int(np.argmax(spectrum))]
    # the real carrier at 0.35, mixed down by the channel's own centre, should be near 0 Hz;
    # its mirror at -0.35 (which would land far from 0 after mixing) must not dominate instead
    assert abs(peak_freq) < 0.05


def test_channel_length_matches_the_detection_span() -> None:
    n = 1 << 18
    x = np.zeros(n, dtype=np.complex128)
    detection = Detection(1000, 200_000, -0.05, 0.05, 4096, 10.0, 20.0, 5)
    channel = channelise(MemorySource(x), detection)
    expected = (detection.stop - detection.start) // channel.decimation
    assert abs(len(channel.samples) - expected) <= 1
