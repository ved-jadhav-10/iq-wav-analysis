"""Detection, checked against dsp.synth ground truth: found bursts match the truth, and a
null (noise-only) recording accepts nothing (PLAN §2 false-accept bar, §5 M2 exit gate)."""

import math
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from dsp.detect import Detection, DetectionResult, detect, detection_parameters
from dsp.evidence import EvidenceLevel
from dsp.synth.chain import Scene, SignalSpec, generate


class MemorySource:
    def __init__(self, x: NDArray[Any]) -> None:
        self.x = x
        self.num_samples = len(x)

    def read(self, start: int, count: int) -> NDArray[Any]:
        return self.x[start : start + count]


def _detect(x: NDArray[Any], *, real: bool = False) -> DetectionResult:
    return detect(MemorySource(x), real=real)


def test_a_single_burst_is_found_with_the_right_band_and_time() -> None:
    spec = SignalSpec("qpsk", sps=8.0, frame=None, offset=0.2, start=5_000, duration=20_000)
    scene = Scene(1 << 16, (spec,), noise_db=-20.0)
    g = generate(scene, seed=1)
    result = _detect(g.samples.astype(np.complex64))
    assert len(result.detections) == 1
    d = result.detections[0]
    bw = (1 / spec.sps) * (1 + spec.rolloff)
    assert d.low < spec.offset - bw / 2 + 0.01
    assert d.high > spec.offset + bw / 2 - 0.01
    assert spec.duration is not None
    assert abs(d.start - spec.start) < 2000
    assert abs(d.stop - (spec.start + spec.duration)) < 2000
    assert d.snr_db > 10


def test_noise_only_recordings_rarely_produce_a_false_detection() -> None:
    """The detector's own false-alarm budget (ALPHA): most noise-only files should have none."""
    false_alarms = 0
    trials = 40
    for seed in range(trials):
        scene = Scene(1 << 15, (), noise_db=0.0)
        g = generate(scene, seed=100 + seed)
        result = _detect(g.samples.astype(np.complex64))
        false_alarms += len(result.detections)
    assert false_alarms / trials < 0.2  # well under 1, for a family-wise ALPHA of 0.01 per file


def test_two_separated_bursts_are_both_found() -> None:
    specs = (
        SignalSpec("bpsk", sps=8.0, frame=None, offset=-0.3, power_db=0.0),
        SignalSpec("qpsk", sps=8.0, frame=None, offset=0.3, power_db=0.0),
    )
    scene = Scene(1 << 16, specs, noise_db=-20.0)
    g = generate(scene, seed=2)
    result = _detect(g.samples.astype(np.complex64))
    assert len(result.detections) == 2
    centres = sorted(d.centre for d in result.detections)
    assert centres[0] == pytest.approx(-0.3, abs=0.02)
    assert centres[1] == pytest.approx(0.3, abs=0.02)


def test_a_weaker_signal_beside_a_much_stronger_one_is_absorbed_as_its_skirt() -> None:
    """A detection whose whole box sits in a much stronger signal's skirt is dropped, not
    reported as a second, weaker signal."""
    specs = (
        SignalSpec("qpsk", sps=16.0, frame=None, offset=-0.06, power_db=0.0),
        SignalSpec("qpsk", sps=16.0, frame=None, offset=0.06, power_db=-25.0),
    )
    scene = Scene(1 << 16, specs, noise_db=-20.0)
    g = generate(scene, seed=3)
    result = _detect(g.samples.astype(np.complex64))
    assert len(result.detections) == 1
    assert result.detections[0].centre == pytest.approx(-0.06, abs=0.02)


def test_real_input_marks_no_image_and_stays_non_negative_in_frequency() -> None:
    x = np.cos(2 * np.pi * 0.15 * np.arange(1 << 15)).astype(np.float64) * 5.0
    rng = np.random.default_rng(0)
    x = x + rng.standard_normal(len(x)) * 0.1
    result = _detect(x, real=True)
    assert all(d.low >= 0 for d in result.detections)
    assert all(d.image_of is None for d in result.detections)


def test_an_8fsk_signals_separate_tones_are_reported_as_one_detection() -> None:
    """Each M-FSK tone is a narrow line with little energy between it and the next, which
    looks like several signals to a plain contiguity test; `merge_tone_combs` must still
    report the carrier as one detection spanning every tone, not one detection per tone.

    Only 8-FSK is exercised end to end here. 2-FSK isn't: with only one gap, there is no
    spacing pattern for `merge_tone_combs` to check (see its docstring), a known, separate
    limitation. 4-FSK isn't either: dsp.synth's `fsk()` shapes no pulse onto the frequency
    trajectory (an abrupt step at each symbol, unlike the RRC-shaped linear modulations), which
    splatters real, above-floor energy between 4-FSK's tones widely enough, and consistently
    enough across seeds, that `merge_tone_combs`' honest "no spacing pattern, no merge" rule
    correctly leaves some of that splatter as its own detection - `test_merge_tone_combs_*`
    below tests the merge logic itself on that exact pattern, without the splatter confound.
    """
    order = 8
    spec = SignalSpec("8fsk", sps=8.0, frame=None, offset=0.05, fsk_index=1.0, power_db=0.0)
    scene = Scene(1 << 16, (spec,), noise_db=-20.0)
    g = generate(scene, seed=order)
    result = _detect(g.samples.astype(np.complex64))
    assert len(result.detections) == 1
    d = result.detections[0]
    deviation = spec.fsk_index / spec.sps
    span = (order - 1) * deviation
    assert d.low < spec.offset - span / 2 + deviation
    assert d.high > spec.offset + span / 2 - deviation


def _tone(centre: float, width: float = 0.002) -> Detection:
    return Detection(0, 65536, centre - width / 2, centre + width / 2, 4096, 20.0, 1000.0, 4)


def _reference() -> Any:
    from dsp.detect import Floor, Resolution
    from dsp.spectrum import Grid, Spectrogram

    grid = Grid(nfft=4096, start=0, frames=1, rows=1)
    freqs = np.fft.fftshift(np.fft.fftfreq(4096))
    power = np.full((1, 4096), 5.0, np.float32)
    spec = Spectrogram(grid, power, power, power, np.array([1]), freqs, False)
    floor = Floor(level=np.ones(4096), global_level=1.0, local_bins=0)
    return Resolution(spec, floor, candidates=0, detections=(), threshold=0.0)


def test_merge_tone_combs_joins_an_evenly_spaced_group_of_a_valid_order() -> None:
    from dsp.detect import merge_tone_combs

    tones = [_tone(c) for c in (-0.1875, -0.0625, 0.0625, 0.1875)]  # a 4-FSK pattern
    merged = merge_tone_combs(tones, _reference())
    assert len(merged) == 1
    assert merged[0].low < -0.1875 and merged[0].high > 0.1875


def test_merge_tone_combs_leaves_an_uneven_or_invalid_count_alone() -> None:
    from dsp.detect import merge_tone_combs

    reference = _reference()
    three = [_tone(c) for c in (-0.2, 0.0, 0.2)]  # not a valid M-FSK order
    assert merge_tone_combs(three, reference) == three

    uneven = [_tone(c) for c in (-0.2, -0.05, 0.0, 0.2)]  # a valid count, unevenly spaced
    assert merge_tone_combs(uneven, reference) == uneven


def test_two_independent_signals_are_not_merged_as_one_fsk_carrier() -> None:
    """Two ordinary signals that happen to share time and rough width aren't a valid M-FSK tone
    count (3), so they stay separate rather than being merged by `merge_tone_combs`."""
    specs = (
        SignalSpec("bpsk", sps=32.0, frame=None, offset=-0.2, power_db=0.0),
        SignalSpec("bpsk", sps=32.0, frame=None, offset=0.0, power_db=0.0),
        SignalSpec("bpsk", sps=32.0, frame=None, offset=0.2, power_db=0.0),
    )
    scene = Scene(1 << 16, specs, noise_db=-20.0)
    g = generate(scene, seed=7)
    result = _detect(g.samples.astype(np.complex64))
    assert len(result.detections) == 3


def test_hypotheses_counts_every_candidate_tried() -> None:
    spec = SignalSpec("qpsk", sps=8.0, frame=None, offset=0.1, power_db=0.0)
    scene = Scene(1 << 15, (spec,), noise_db=-20.0)
    g = generate(scene, seed=42)
    result = _detect(g.samples.astype(np.complex64))
    assert result.hypotheses == sum(r.candidates for r in result.resolutions)
    assert result.hypotheses > 0  # at least the true signal's own candidate, at every FFT size


def test_detection_parameters_report_the_detections_own_values() -> None:
    d = Detection(
        start=1_000,
        stop=5_000,
        low=-0.1,
        high=0.1,
        nfft=1024,
        snr_db=12.0,
        score=50.0,
        cells=64,
        dof=500.0,
        time_resolution=800,
    )
    params = {p.id: p for p in detection_parameters(d)}
    assert set(params) == {"center_frequency", "bandwidth", "start_sample", "stop_sample", "snr_db"}
    assert params["center_frequency"].value == d.centre
    assert params["bandwidth"].value == d.bandwidth
    assert params["start_sample"].value == d.start
    assert params["stop_sample"].value == d.stop
    assert params["snr_db"].value == d.snr_db
    for p in params.values():
        assert p.level is EvidenceLevel.ESTIMATED
        assert p.uncertainty is not None
    assert not params["snr_db"].warnings[1:]  # only the always-present detector-bias warning
    # start/stop uncertainty is half the *time grid's* row width (d.time_resolution), not nfft.
    assert params["start_sample"].uncertainty == pytest.approx(400.0)
    assert params["stop_sample"].uncertainty == pytest.approx(400.0)
    # snr uncertainty: 4.343 (1+s)/(s sqrt(dof)), s = 10**(snr_db/10) - not the old, wrong
    # 4.343/sqrt(cells), which for these values would give 4.343/8 = 0.543.
    s = 10 ** (d.snr_db / 10)
    expected_snr_uncertainty = 4.343 * (1 + s) / (s * math.sqrt(d.dof))
    assert params["snr_db"].uncertainty == pytest.approx(expected_snr_uncertainty)


def test_detection_parameters_snr_uncertainty_brackets_the_true_spread() -> None:
    """The stated snr_db uncertainty should be the right order of magnitude for the actual
    spread across independent draws at the same SNR - not just present (PLAN's "never it didn't
    crash" rule applies to a stated uncertainty too, not only to the value itself)."""
    spec = SignalSpec("qpsk", sps=8.0, frame=None, offset=0.1, power_db=0.0)
    scene = Scene(1 << 16, (spec,), noise_db=-12.0)
    found = []
    for seed in range(20):
        g = generate(scene, seed=seed)
        result = _detect(g.samples.astype(np.complex64))
        d = min(result.detections, key=lambda d: abs(d.centre - spec.offset))
        found.append(d)
    snrs = np.array([d.snr_db for d in found])
    actual_std = float(np.std(snrs))
    stated = np.array([detection_parameters(d)[4].uncertainty for d in found])
    assert np.all(stated > 0)
    # within a factor of 4 either way: a loose bound (the formula is an approximation, checked
    # more precisely in scratch validation against dsp.synth over 0-30 dB), just enough to catch
    # a formula off by an order of magnitude (dsp-reviewer's finding on the previous version).
    assert 0.25 * actual_std < float(np.median(stated)) < 4.0 * actual_std


def test_detection_parameters_warn_when_marked_as_an_image() -> None:
    d = Detection(
        start=0,
        stop=100,
        low=-0.05,
        high=0.05,
        nfft=256,
        snr_db=5.0,
        score=10.0,
        cells=8,
        image_of=0,
    )
    params = {p.id: p for p in detection_parameters(d)}
    assert any("image" in w for w in params["snr_db"].warnings)
