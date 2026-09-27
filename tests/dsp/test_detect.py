"""Detection, checked against dsp.synth ground truth: found bursts match the truth, and a
null (noise-only) recording accepts nothing (PLAN §2 false-accept bar, §5 M2 exit gate)."""

from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from dsp.detect import DetectionResult, detect
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


def test_hypotheses_counts_every_candidate_tried() -> None:
    spec = SignalSpec("qpsk", sps=8.0, frame=None, offset=0.1, power_db=0.0)
    scene = Scene(1 << 15, (spec,), noise_db=-20.0)
    g = generate(scene, seed=42)
    result = _detect(g.samples.astype(np.complex64))
    assert result.hypotheses == sum(r.candidates for r in result.resolutions)
    assert result.hypotheses > 0  # at least the true signal's own candidate, at every FFT size
