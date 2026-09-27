import numpy as np
import pytest

from dsp.synth.waveforms import awgn, fsk, psk_symbols, rrc_taps, shape, tone


def test_rrc_is_unit_energy_symmetric_and_nyquist_when_matched() -> None:
    sps, span = 8, 16
    h = rrc_taps(sps, 0.35, span)
    assert np.sum(h**2) == pytest.approx(1.0)
    np.testing.assert_allclose(h, h[::-1])
    raised_cosine = np.convolve(h, h)
    centre = len(raised_cosine) // 2
    assert raised_cosine[centre] == pytest.approx(1.0, abs=1e-3)
    others = raised_cosine[centre % sps :: sps]
    others = np.delete(others, centre // sps)
    assert np.max(np.abs(others)) < 2e-3  # zero ISI at every other symbol instant


def test_rrc_handles_the_singular_points() -> None:
    h = rrc_taps(4, 0.25)  # t = ±1/(4β) = ±1 symbol falls exactly on a tap
    assert np.all(np.isfinite(h))
    with pytest.raises(ValueError, match="rolloff"):
        rrc_taps(4, 0.0)


def test_matched_filter_recovers_the_symbols_exactly() -> None:
    rng = np.random.default_rng(3)
    sps, span = 4, 16
    symbols = psk_symbols(rng, 200, 4)
    x = shape(symbols, sps, 0.35, span)
    y = np.convolve(x, rrc_taps(sps, 0.35, span)) / np.sqrt(sps)
    delay = span * sps  # half a pulse from shaping plus half from matching
    recovered = y[delay : delay + len(symbols) * sps : sps]
    np.testing.assert_allclose(recovered[span:-span], symbols[span:-span], atol=5e-3)


def test_qpsk_symbols_sit_on_the_diagonals() -> None:
    symbols = psk_symbols(np.random.default_rng(0), 1000, 4)
    angles = np.round(np.degrees(np.angle(symbols))).astype(int)
    assert set(angles) == {45, 135, -45, -135}


def test_tone_is_at_its_frequency() -> None:
    n, frequency = 4096, 0.125
    spectrum = np.abs(np.fft.fft(tone(n, frequency)))
    assert np.argmax(spectrum) == int(frequency * n)


def test_awgn_has_the_requested_power_and_is_seeded() -> None:
    x = awgn(np.random.default_rng(5), 200_000, power=0.5)
    assert np.mean(np.abs(x) ** 2) == pytest.approx(0.5, rel=0.01)
    np.testing.assert_array_equal(x, awgn(np.random.default_rng(5), 200_000, power=0.5))


def test_fsk_tones_are_at_the_stated_deviation() -> None:
    x = fsk(np.random.default_rng(1), 400, 2, 8, 0.05)
    inst = np.angle(x[1:] * np.conj(x[:-1])) / (2 * np.pi)
    assert set(np.round(inst, 6)) == {-0.05, 0.05}
