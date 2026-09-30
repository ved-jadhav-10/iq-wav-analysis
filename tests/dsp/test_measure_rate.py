"""`measure_symbol_rate`: the |x|² line alone, for the structural sample-rate test (PLAN M2)."""

import math
from typing import Any

import numpy as np
import pytest

from dsp.analyse import measure_symbol_rate
from dsp.detect import Detection, detect
from dsp.synth.chain import Scene, SignalSpec, generate


class Memory:
    def __init__(self, x: Any) -> None:
        self.x = np.asarray(x)
        self.num_samples = len(self.x)

    def read(self, start: int, count: int) -> Any:
        return self.x[start : start + count]


def strongest(source: Memory) -> Detection:
    found = detect(source, real=False).detections
    assert found
    return max(found, key=lambda d: d.bandwidth * (d.stop - d.start))


@pytest.mark.parametrize(("modulation", "sps"), [("bpsk", 250), ("qpsk", 40), ("qpsk", 16)])
def test_the_rate_is_the_transmitted_one_to_a_few_parts_per_million(
    modulation: str, sps: int
) -> None:
    spec = SignalSpec(modulation, sps=sps, power_db=-5 - 10 * math.log10(sps), offset=0.1)
    g = generate(Scene(1 << 19, (spec,), noise_db=-20.0), seed=3)
    source = Memory(g.samples)
    measured = measure_symbol_rate(source, strongest(source))
    assert measured is not None
    rate, relative = measured
    assert rate * sps == pytest.approx(1.0, abs=2e-5)  # in symbols per input sample
    assert relative < 1e-4


def test_a_constant_envelope_has_no_symbol_rate_line_to_measure() -> None:
    """A noiseless tone's |x|² is constant, so the line the estimator finds there is rounding."""
    rng = np.random.default_rng(2)
    n = 1 << 16
    tone = np.exp(2j * np.pi * 0.1 * np.arange(n)) * (1 + 1e-9 * rng.normal(size=n))
    source = Memory(tone + 1e-7 * (rng.normal(size=n) + 1j * rng.normal(size=n)))
    found = detect(source, real=False).detections
    assert found
    assert all(measure_symbol_rate(source, d) is None for d in found)
