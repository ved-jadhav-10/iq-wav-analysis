"""Analog AM/FM detection, checked against dsp.synth ground truth (PLAN §5 M2)."""

import pytest

from dsp.analog import analog_detect
from dsp.synth.chain import Scene, SignalSpec, generate


def _noise_power(noise_db: float) -> float:
    return 10 ** (noise_db / 10)


@pytest.mark.parametrize("snr_db", [15.0, 20.0, 30.0])
def test_am_is_detected_at_good_snr(snr_db: float) -> None:
    spec = SignalSpec("am", offset=0.0, frame=None, audio_bandwidth=0.02)
    scene = Scene(1 << 15, (spec,), noise_db=-snr_db)
    g = generate(scene, seed=5)
    result = analog_detect(g.samples, _noise_power(-snr_db))
    assert result is not None
    assert result.kind == "am"


def test_fm_is_detected_at_good_snr_with_a_clear_deviation() -> None:
    spec = SignalSpec("fm", offset=0.0, frame=None, audio_bandwidth=0.02, fm_deviation=0.08)
    scene = Scene(1 << 15, (spec,), noise_db=-30.0)
    g = generate(scene, seed=5)
    result = analog_detect(g.samples, _noise_power(-30.0))
    assert result is not None
    assert result.kind == "fm"


@pytest.mark.parametrize("snr_db", [0.0, 6.0, 10.0])
def test_am_abstains_rather_than_guessing_at_low_snr(snr_db: float) -> None:
    """A margin the modulation can't clearly clear should abstain, not guess (CLAUDE.md: a
    stage must have a case where it fails or abstains, not only cases where it succeeds)."""
    spec = SignalSpec("am", offset=0.0, frame=None, audio_bandwidth=0.02)
    scene = Scene(1 << 15, (spec,), noise_db=-snr_db)
    g = generate(scene, seed=5)
    result = analog_detect(g.samples, _noise_power(-snr_db))
    assert result is None


def test_pure_noise_is_never_called_am_or_fm() -> None:
    for seed in range(10):
        scene = Scene(1 << 14, (), noise_db=0.0)
        g = generate(scene, seed=100 + seed)
        assert analog_detect(g.samples, _noise_power(0.0)) is None


def test_a_digital_signal_is_never_called_am_or_fm() -> None:
    for modulation in ("bpsk", "qpsk", "16qam", "2fsk"):
        spec = SignalSpec(modulation, sps=8.0, frame=None, offset=0.0)
        scene = Scene(1 << 15, (spec,), noise_db=-20.0)
        g = generate(scene, seed=5)
        assert analog_detect(g.samples, _noise_power(-20.0)) is None


def test_fsk_is_not_mistaken_for_fm_even_though_both_are_constant_envelope() -> None:
    """M-FSK is constant-envelope and frequency-varying, FM's own signature; only the discrete
    tones' below-Gaussian kurtosis tells them apart (FSK_KURTOSIS_GATE)."""
    for modulation in ("2fsk", "4fsk", "8fsk"):
        spec = SignalSpec(modulation, sps=8.0, frame=None, offset=0.0)
        scene = Scene(1 << 15, (spec,), noise_db=-20.0)
        g = generate(scene, seed=5)
        result = analog_detect(g.samples, _noise_power(-20.0))
        assert result is None or result.kind != "fm"
