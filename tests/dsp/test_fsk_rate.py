"""The FSK symbol-rate estimator at high oversampling (PLAN M3): the per-sample discriminator's
noise grows with samples per symbol, so the multi-scale discriminator must still put the true
rate among the candidates, and the chain must still reach FSK and a known system."""

import math
from typing import Any

import numpy as np
import pytest

from dsp.analyse import analyse
from dsp.channel import channelise
from dsp.detect import detect
from dsp.estimate.params import fsk_symbol_rates
from dsp.evidence import EvidenceLevel
from dsp.synth.chain import Scene, SignalSpec, generate
from dsp.synth.systems import Navtex

NOISE_DB = -20.0


class Memory:
    def __init__(self, x: Any) -> None:
        self.x = np.asarray(x)
        self.num_samples = len(self.x)

    def read(self, start: int, count: int) -> Any:
        return self.x[start : start + count]


def _scene(modulation: str, sps: int, esn0_db: float, seed: int = 5, **spec: Any) -> Any:
    power = NOISE_DB + esn0_db - 10 * math.log10(sps)
    signal = SignalSpec(
        modulation=modulation,
        sps=sps,
        fsk_index=1.0,
        power_db=power,
        start=2000,
        duration=(1 << 18) - 4000,
        **spec,
    )
    return generate(
        Scene(samples=1 << 18, signals=(signal,), noise_db=NOISE_DB, sample_rate=100.0 * sps), seed
    )


def _channel(g: Any) -> Any:
    source = Memory(g.samples)
    detections = detect(source, real=False).detections
    main = max(detections, key=lambda d: (d.stop - d.start) * (d.high - d.low))
    return source, main, channelise(source, main)


@pytest.mark.parametrize(
    ("modulation", "sps", "esn0"),
    [
        ("2fsk", 16, 15.0),
        ("2fsk", 32, 15.0),
        ("4fsk", 16, 18.0),
        ("4fsk", 32, 18.0),
        ("8fsk", 16, 22.0),
        ("8fsk", 32, 22.0),
        ("8fsk", 64, 22.0),
    ],
)
def test_the_true_symbol_rate_is_among_the_candidates_at_high_oversampling(
    modulation: str, sps: int, esn0: float
) -> None:
    """The channel is what the chain hands the estimator (decimated to its bandwidth); the
    per-sample discriminator finds no line in several of these."""
    _, _, channel = _channel(_scene(modulation, sps, esn0))
    true = channel.decimation / sps  # symbols per channel sample
    found = fsk_symbol_rates(channel.samples)
    assert found, "at least one candidate"
    assert any(abs(r.normalised_rate - true) <= 0.01 * true for r in found), (
        f"true {1 / true:.2f} samples per symbol not among "
        f"{[round(1 / r.normalised_rate, 2) for r in found]}"
    )


def test_noise_alone_gives_no_candidates() -> None:
    rng = np.random.default_rng(1)
    for n in (1 << 15, 1 << 17):
        x = rng.standard_normal(n) + 1j * rng.standard_normal(n)
        assert fsk_symbol_rates(x.astype(np.complex128)) == []


@pytest.mark.parametrize("sps", [16, 32])
def test_a_navtex_recording_at_high_oversampling_reaches_the_system_through_the_chain(
    sps: int,
) -> None:
    g = _scene("2fsk", sps, 15.0, frame=None, system=Navtex())
    source, main, _ = _channel(g)
    report = analyse(source, main, sample_rate=100.0 * sps)
    assert report.kind == "fsk" and report.level is EvidenceLevel.VERIFIED
    system = next(
        p for s in report.stages if s.id == "match" for p in s.parameters if p.id == "system"
    )
    assert system.level is EvidenceLevel.VERIFIED and system.value == "NAVTEX (SITOR-B)"
    # The rate is stated in baud from the sample rate: 100 Bd whatever the oversampling.
    rate = next(
        p
        for s in report.stages
        if s.id == "estimate"
        for p in s.parameters
        if p.id == "symbol_rate"
    )
    assert rate.unit == "Bd" and isinstance(rate.value, float)
    assert rate.value == pytest.approx(100.0, rel=0.02)
