"""The eye diagram of a decoded QPSK signal, against the shape ground truth says it must have."""

import math

import numpy as np
import pytest

from dsp.analyse import analyse
from dsp.detect import detect
from dsp.eye import EYE_SPS, EYE_TRACES, eye_diagram
from dsp.report import Eye
from dsp.sync import Timing
from dsp.synth.chain import Scene, SignalSpec, generate


class Memory:
    def __init__(self, x: np.ndarray) -> None:
        self.x = x
        self.num_samples = len(x)

    def read(self, start: int, count: int) -> np.ndarray:
        return self.x[start : start + count]


def _eye(modulation: str, esn0_db: float) -> Eye:
    sps = 8
    power = -20.0 + esn0_db - 10 * math.log10(sps)
    spec = SignalSpec(modulation, sps=float(sps), power_db=power, offset=0.1, frame=None)
    g = generate(Scene(samples=1 << 17, signals=(spec,), noise_db=-20.0), seed=3)
    source = Memory(g.samples)
    main = max(detect(source, real=False).detections, key=lambda d: d.stop - d.start)
    report = analyse(source, main)
    assert report.eye is not None
    return report.eye


def test_a_clean_qpsk_eye_is_open_at_the_symbol_instant_and_closes_between_symbols() -> None:
    eye = _eye("qpsk", 30.0)
    i, q = np.array(eye.i), np.array(eye.q)
    assert i.shape == q.shape == (EYE_TRACES, 2 * EYE_SPS + 1)
    centre = EYE_SPS
    # At the symbol instant every trace sits on one of the two levels +-1/sqrt(2) of each axis
    # (unit-RMS QPSK), whichever way the carrier ambiguity turned them.
    for axis in (i, q):
        assert np.allclose(np.abs(axis[:, centre]), 1 / math.sqrt(2), atol=0.08)
    # Half a symbol away the traces cross: transitions pass through zero, so the spread of
    # |level| is wide there and narrow at the instant.
    half = centre + EYE_SPS // 2
    assert np.std(np.abs(i[:, half])) > 4 * np.std(np.abs(i[:, centre]))
    # About symmetric in time (a raised-cosine eye is); the timing loop's residual offset of a
    # few hundredths of a symbol is the difference.
    left, right = np.mean(np.abs(i[:, centre - 3])), np.mean(np.abs(i[:, centre + 3]))
    assert left == pytest.approx(right, abs=0.12)


def test_noise_closes_the_eye() -> None:
    clean, noisy = _eye("qpsk", 30.0), _eye("qpsk", 12.0)

    def spread(eye: Eye) -> float:
        return float(np.std(np.abs(np.array(eye.i)[:, EYE_SPS])))

    assert spread(noisy) > 3 * spread(clean)


def test_the_eye_needs_enough_symbols_and_matching_lengths() -> None:
    timing = Timing(np.ones(10, np.complex128), 0.1, 0.0, 0.0)
    assert eye_diagram(timing, np.ones(10, np.complex128)) is None
    long = Timing(np.ones(100, np.complex128), 0.1, 0.0, 0.0)
    assert eye_diagram(long, np.ones(100, np.complex128)) is None  # no matched-filter output kept


def test_an_eye_with_ragged_traces_is_refused() -> None:
    with pytest.raises(ValueError, match="17 points"):
        Eye(samples_per_symbol=8, i=((0.0,) * 17, (0.0,) * 16), q=((0.0,) * 17, (0.0,) * 17))
