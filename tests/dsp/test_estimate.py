"""Line search and parameter estimation, checked against dsp.synth ground truth."""

import numpy as np
import pytest

from dsp.estimate.lines import find_lines
from dsp.estimate.params import (
    carrier_offset,
    fsk_symbol_rate,
    occupied_bandwidth,
    rolloff_fit,
    snr_psd,
    symbol_rate,
)
from dsp.spectrum import welch, welch_dof
from dsp.synth.chain import Scene, SignalSpec, generate

# -- lines.py -------------------------------------------------------------------------------


def test_find_lines_locates_an_exact_tone_and_bounds_its_uncertainty() -> None:
    n = 1 << 14
    freq = 0.1237
    x = np.exp(2j * np.pi * freq * np.arange(n))
    search = find_lines(x, -0.5, 0.5)
    assert search.strongest is not None
    assert search.strongest.frequency == pytest.approx(freq, abs=1e-4)
    assert search.strongest.uncertainty < 1e-3


def test_find_lines_reports_nothing_in_pure_noise() -> None:
    rng = np.random.default_rng(0)
    x = rng.standard_normal(1 << 12) + 1j * rng.standard_normal(1 << 12)
    search = find_lines(x, -0.5, 0.5, alpha=0.01)
    assert search.lines == ()


def test_exclude_removes_a_band_from_the_search() -> None:
    n = 1 << 14
    x = np.exp(2j * np.pi * 0.2 * np.arange(n))
    search = find_lines(x, -0.5, 0.5, exclude=((0.15, 0.25),))
    assert search.lines == ()


# -- params.py: symbol rate, CFO --------------------------------------------------------------


@pytest.mark.parametrize("modulation,sps", [("bpsk", 4.0), ("qpsk", 8.0), ("8psk", 4.0)])
def test_symbol_rate_matches_the_true_rate(modulation: str, sps: float) -> None:
    spec = SignalSpec(modulation, sps=sps, frame=None, offset=0.05)
    scene = Scene(1 << 17, (spec,), noise_db=-15.0)
    g = generate(scene, seed=7)
    result = symbol_rate(g.samples)
    assert result is not None
    assert result.normalised_rate == pytest.approx(1 / sps, abs=1e-4)


def test_fsk_symbol_rate_matches_the_true_rate() -> None:
    spec = SignalSpec("2fsk", sps=8.0, frame=None, offset=0.0)
    scene = Scene(1 << 17, (spec,), noise_db=-15.0)
    g = generate(scene, seed=7)
    result = fsk_symbol_rate(g.samples)
    assert result is not None
    assert result.normalised_rate == pytest.approx(1 / 8.0, abs=1e-3)


@pytest.mark.parametrize("modulation,order", [("bpsk", 2), ("qpsk", 4)])
def test_carrier_offset_matches_the_true_cfo(modulation: str, order: int) -> None:
    cfo = 0.013
    spec = SignalSpec(modulation, sps=4.0, frame=None, offset=cfo)
    scene = Scene(1 << 17, (spec,), noise_db=-15.0)
    g = generate(scene, seed=7)
    result = carrier_offset(g.samples, modulation)
    assert result is not None
    assert result.order == order
    assert result.cfo == pytest.approx(cfo, abs=1e-4)


def test_carrier_offset_is_gated_off_for_qam() -> None:
    spec = SignalSpec("16qam", sps=4.0, frame=None, offset=0.02)
    scene = Scene(1 << 16, (spec,), noise_db=-15.0)
    g = generate(scene, seed=7)
    assert carrier_offset(g.samples, "16qam") is None


def test_carrier_offset_is_not_attempted_for_8psk() -> None:
    """8-PSK's 8th power is too weak on a pulse-shaped waveform to be worth chasing (M2 limit)."""
    spec = SignalSpec("8psk", sps=4.0, frame=None, offset=0.02)
    scene = Scene(1 << 16, (spec,), noise_db=-15.0)
    g = generate(scene, seed=7)
    assert carrier_offset(g.samples, "8psk") is None


# -- params.py: occupied bandwidth, SNR, roll-off --------------------------------------------


def test_occupied_bandwidth_matches_the_nominal_rrc_bandwidth() -> None:
    sps, rolloff = 4.0, 0.35
    spec = SignalSpec("qpsk", sps=sps, frame=None, offset=0.0, rolloff=rolloff)
    scene = Scene(1 << 17, (spec,), noise_db=-25.0)
    g = generate(scene, seed=7)
    psd = welch(g.samples, 4096)
    freqs = np.fft.fftshift(np.fft.fftfreq(len(psd)))
    obw = occupied_bandwidth(psd, freqs, dof=welch_dof(len(g.samples), 4096))
    nominal = (1 / sps) * (1 + rolloff)
    assert obw.bandwidth < nominal  # 99% energy sits inside the full-support bandwidth
    assert obw.bandwidth > 0.5 * nominal


@pytest.mark.parametrize("esn0_db", [15.0, 20.0])
def test_snr_estimate_is_within_a_couple_db_at_high_snr(esn0_db: float) -> None:
    sps = 8.0
    spec = SignalSpec("qpsk", sps=sps, frame=None, offset=0.0)
    noise_db = -esn0_db + 10 * np.log10(sps)
    scene = Scene(1 << 17, (spec,), noise_db=noise_db)
    g = generate(scene, seed=11)
    result = snr_psd(g.samples, 4096)
    assert result.snr_db == pytest.approx(esn0_db, abs=2.0)


def test_snr_estimate_degrades_but_stays_in_the_right_range_at_low_snr() -> None:
    """Documented limit: a single PSD-based estimator, with no M2M4 or eigenvalue cross-check
    yet (PLAN §5 M2), loses accuracy as the occupied bandwidth it depends on gets harder to
    measure. It should still land in the right neighbourhood, not collapse to nonsense."""
    sps = 8.0
    esn0_db = 10.0
    spec = SignalSpec("qpsk", sps=sps, frame=None, offset=0.0)
    noise_db = -esn0_db + 10 * np.log10(sps)
    scene = Scene(1 << 17, (spec,), noise_db=noise_db)
    g = generate(scene, seed=11)
    result = snr_psd(g.samples, 4096)
    assert result.snr_db == pytest.approx(esn0_db, abs=8.0)


@pytest.mark.parametrize("rolloff", [0.2, 0.25, 0.35, 0.5])
def test_rolloff_fit_recovers_the_true_value(rolloff: float) -> None:
    sps = 4.0
    spec = SignalSpec("bpsk", sps=sps, frame=None, offset=0.0, rolloff=rolloff)
    scene = Scene(1 << 17, (spec,), noise_db=-25.0)
    g = generate(scene, seed=7)
    psd = welch(g.samples, 4096)
    freqs = np.fft.fftshift(np.fft.fftfreq(len(psd)))
    beta = rolloff_fit(psd, freqs, 1 / sps)
    assert beta == pytest.approx(rolloff)
