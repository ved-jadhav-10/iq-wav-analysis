"""Analog AM/FM detection, checked against dsp.synth ground truth (PLAN §5 M2)."""

from typing import Any

import numpy as np
import pytest

from dsp.analog import analog_detect, measure_analog
from dsp.synth.chain import Scene, SignalSpec, generate
from dsp.synth.impair import awgn
from dsp.synth.modulate import am, audio, fm


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


# -- measurements, against a message whose statistics are known exactly -------------------------


def _am_signal(
    snr_db: float, depth: float, bandwidth: float, offset: float = 0.0
) -> tuple[Any, float]:
    """AM with a known message: the carrier's complex samples and the RMS of the normalised
    message times the depth (the truth `measure_analog` should report)."""
    rng = np.random.default_rng(7)
    n = 1 << 16
    message = audio(rng, n, bandwidth)
    norm = message / np.max(np.abs(message))
    x = am(message, depth) * np.exp(2j * np.pi * offset * np.arange(n))
    x = x + awgn(rng, n, 10 ** (-snr_db / 10))
    return x, depth * float(np.std(norm))


@pytest.mark.parametrize(("depth", "bandwidth"), [(0.8, 0.02), (0.5, 0.04), (0.9, 0.01)])
def test_am_depth_audio_bandwidth_and_carrier_are_measured(depth: float, bandwidth: float) -> None:
    x, truth_rms = _am_signal(35.0, depth, bandwidth, offset=0.013)
    result = analog_detect(x, 10 ** (-35.0 / 10))
    assert result is not None and result.kind == "am"
    m = measure_analog(x, result)
    assert m.am_depth_rms == pytest.approx(truth_rms, rel=0.1)
    assert m.audio_bandwidth == pytest.approx(bandwidth, rel=0.25)
    assert m.carrier_offset == pytest.approx(0.013, abs=2e-4)
    assert m.fm_deviation_rms is None


@pytest.mark.parametrize("deviation", [0.05, 0.08, 0.12])
def test_fm_rms_deviation_and_carrier_are_measured(deviation: float) -> None:
    rng = np.random.default_rng(3)
    n = 1 << 16
    message = audio(rng, n, 0.02)
    truth_rms = deviation * float(np.std(message / np.max(np.abs(message))))
    x = fm(message, deviation) * np.exp(2j * np.pi * -0.021 * np.arange(n))
    x = x + awgn(rng, n, 10 ** (-35.0 / 10))
    result = analog_detect(x, 10 ** (-35.0 / 10))
    assert result is not None and result.kind == "fm"
    m = measure_analog(x, result)
    assert m.fm_deviation_rms == pytest.approx(truth_rms, rel=0.1)
    assert m.carrier_offset == pytest.approx(-0.021, abs=2e-3)  # the mean of a moving message
    assert m.am_depth_rms is None and m.audio_bandwidth is None


def test_the_chain_reports_an_analog_signals_measurements_as_parameters() -> None:
    from dsp.analyse import analyse
    from dsp.detect import detect

    class Memory:
        def __init__(self, x: Any) -> None:
            self.x = np.asarray(x)
            self.num_samples = len(self.x)

        def read(self, start: int, count: int) -> Any:
            return self.x[start : start + count]

    spec = SignalSpec(
        "am", offset=0.1, frame=None, audio_bandwidth=0.01, power_db=-10.0, am_depth=0.8
    )
    g = generate(Scene(1 << 17, (spec,), noise_db=-45.0), seed=5)
    source = Memory(g.samples)
    detections = detect(source, real=False).detections
    main = max(detections, key=lambda d: (d.stop - d.start) * (d.high - d.low))
    report = analyse(source, main)
    assert report.kind == "analog" and report.label == "AM"
    estimate = next(s for s in report.stages if s.id == "estimate")
    ids = {p.id for p in estimate.parameters}
    assert {"carrier", "bandwidth", "am_depth", "audio_bandwidth"} <= ids
    carrier = next(p for p in estimate.parameters if p.id == "carrier")
    assert carrier.value == pytest.approx(0.1, abs=2e-3)
    assert all(p.uncertainty is not None for p in estimate.parameters)
