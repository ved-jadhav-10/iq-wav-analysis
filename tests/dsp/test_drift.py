"""Carrier drift (PLAN M3): how much of a Doppler ramp the chain's carrier tracking takes."""

import math
from typing import Any

import numpy as np
import pytest

from dsp.analyse import analyse
from dsp.detect import detect
from dsp.evidence import EvidenceLevel
from dsp.synth import fec
from dsp.synth.chain import Scene, SignalSpec, generate
from dsp.synth.impair import Impairments, apply

CONV = fec.Convolutional(7, fec.K7)


class Memory:
    def __init__(self, x: Any) -> None:
        self.x = np.asarray(x)
        self.num_samples = len(self.x)

    def read(self, start: int, count: int) -> Any:
        return self.x[start : start + count]


def test_the_drift_impairment_is_a_quadratic_phase() -> None:
    n = np.arange(1000)
    y = apply(
        np.ones(1000, np.complex128), Impairments(cfo=0.01, cfo_rate=2e-6), np.random.default_rng(0)
    )
    expected = 2 * np.pi * (0.01 * n + 0.5 * 2e-6 * n.astype(np.float64) ** 2)
    assert np.allclose(np.unwrap(np.angle(y)), expected, atol=1e-6)
    assert Impairments(cfo_rate=1e-9).truth()["cfo_rate"] == 1e-9


@pytest.mark.parametrize(("rate", "least_share"), [(0.0, 0.9), (1e-10, 0.9), (1e-9, 0.7)])
def test_the_chain_decodes_through_a_carrier_ramp(rate: float, least_share: float) -> None:
    """Measured limit: a drift of 1e-9 cycles/sample² (2e-4 cycles/sample over the 200,000-sample
    burst, 8 samples a symbol) still verifies with at least 70 % of the frames passing. About
    1e-8 leaves half, and 3e-8 loses the signal (the per-block carrier phase no longer unwraps)."""
    spec = SignalSpec(
        "qpsk",
        sps=8,
        power_db=-20 + 15 - 10 * math.log10(8),
        inner=CONV,
        stream_offset=3,
        offset=0.1,
        start=10_000,
        duration=200_000,
        impairments=Impairments(cfo_rate=rate),
    )
    g = generate(Scene(samples=1 << 18, signals=(spec,), noise_db=-20.0), 7)
    source = Memory(g.samples)
    main = max(
        detect(source, real=False).detections, key=lambda d: (d.stop - d.start) * (d.high - d.low)
    )
    report = analyse(source, main)
    assert report.level is EvidenceLevel.VERIFIED and report.label == "QPSK"
    passing = sum(f.crc == "pass" for f in report.frames)
    assert passing >= least_share * len(report.frames)
