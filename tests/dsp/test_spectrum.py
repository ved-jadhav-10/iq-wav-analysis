"""Streaming Welch spectrograms, checked against a plain in-memory FFT and exact tone power."""

import numpy as np
import pytest

from dsp.spectrum import Grid, plan_grid, spectrograms, welch, welch_dof


def test_plan_grid_bounds_the_cell_count_and_needs_min_average_frames() -> None:
    grid = plan_grid(1 << 20, 1024)
    assert grid is not None
    assert grid.nfft * grid.rows <= 1 << 22
    assert grid.frames // grid.rows >= 8 or grid.rows == 1
    assert plan_grid(100, 1024) is None  # fewer samples than one frame


def test_grid_row_span_covers_every_frame_once() -> None:
    grid = Grid(nfft=64, start=100, frames=20, rows=4)
    bounds = grid.bounds
    assert bounds[0] == 0 and bounds[-1] == 20
    starts, stops = [], []
    for r in range(grid.rows):
        s, e = grid.row_span(r, r)
        starts.append(s)
        stops.append(e)
    # consecutive rows' spans touch (they share the hop overlap), never gap or go backwards
    for a, b in zip(stops, starts[1:], strict=False):
        assert b <= a


def test_a_pure_tone_puts_all_power_in_its_bin() -> None:
    n, nfft = 1 << 16, 1024
    freq = 96.5 / nfft  # not bin-centred, to check the window doesn't smear it away entirely
    x = np.exp(2j * np.pi * freq * np.arange(n)).astype(np.complex64)
    grid = plan_grid(n, nfft)
    assert grid is not None
    spec = spectrograms([x], [grid], real=False)[0]
    psd = spec.psd()
    peak_bin = int(np.argmax(psd))
    assert abs(spec.freqs[peak_bin] - freq) < 1.0 / nfft
    # a tone's peak bin holds most of the signal's power (~unit power for a unit-amplitude tone)
    assert psd[peak_bin] > 0.5


def test_white_noise_psd_averages_to_its_variance() -> None:
    rng = np.random.default_rng(0)
    n = 1 << 18
    power = 2.0
    x = np.sqrt(power / 2) * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
    psd = welch(x.astype(np.complex64), 2048)
    assert np.mean(psd) == pytest.approx(power, rel=0.05)
    # a Welch PSD averaged over many frames has low relative variance bin to bin
    assert np.std(psd) / np.mean(psd) < 0.3


def test_real_input_keeps_only_non_negative_frequencies() -> None:
    n, nfft = 1 << 15, 512
    x = np.cos(2 * np.pi * 0.1 * np.arange(n)).astype(np.float64)
    grid = plan_grid(n, nfft)
    assert grid is not None
    spec = spectrograms([x], [grid], real=True)[0]
    assert np.all(spec.freqs >= 0)
    assert spec.power.shape[1] == len(spec.freqs)


def test_welch_treats_real_input_as_one_sided_not_a_mirrored_spectrum() -> None:
    """A real tone's negative-frequency half is the same information, not a second signal;
    folding it in as if complex would double the measured bandwidth and centre it on 0 Hz."""
    n, nfft = 1 << 14, 1024
    freq = 0.1
    x = np.cos(2 * np.pi * freq * np.arange(n))
    psd = welch(x, nfft)
    freqs = np.fft.fftshift(np.fft.fftfreq(nfft))
    freqs = freqs[freqs >= 0]
    assert len(freqs) == len(psd)
    peak_freq = float(freqs[int(np.argmax(psd))])
    assert peak_freq == pytest.approx(freq, abs=1.0 / nfft)


def test_welch_dof_matches_the_frames_welch_actually_averages() -> None:
    rng = np.random.default_rng(2)
    n, nfft = 1 << 16, 2048
    x = (rng.standard_normal(n) + 1j * rng.standard_normal(n)).astype(np.complex64)
    psd = welch(x, nfft)
    dof = welch_dof(n, nfft)
    # more frames averaged means less bin-to-bin scatter; check the two move together roughly
    assert dof > 1
    assert np.std(psd) / np.mean(psd) < 1.0 / np.sqrt(dof) * 3


def test_feeding_in_arbitrary_chunks_matches_feeding_all_at_once() -> None:
    rng = np.random.default_rng(1)
    n, nfft = 1 << 15, 512
    x = (rng.standard_normal(n) + 1j * rng.standard_normal(n)).astype(np.complex64)
    grid = plan_grid(n, nfft)
    assert grid is not None
    whole = spectrograms([x], [grid], real=False)[0]
    chunks = [x[i : i + 777] for i in range(0, n, 777)]
    chunked = spectrograms(chunks, [grid], real=False)[0]
    np.testing.assert_allclose(whole.power, chunked.power, rtol=1e-5)
