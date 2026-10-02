"""Offset QPSK (PLAN M3): the generator, the x² line-pair estimator, the timing that reads Q half
a symbol after I, and the chain end to end, all against dsp.synth's exact truth."""

import math
from dataclasses import replace
from math import erfc, sqrt
from typing import Any

import numpy as np
import pytest

from dsp.analyse import analyse
from dsp.demod import demap, rotate, rotations
from dsp.detect import detect
from dsp.estimate.offset import offset_symbol_rate
from dsp.evidence import EvidenceLevel
from dsp.report import DetectionReport
from dsp.sync import correct_carrier, recover_timing
from dsp.synth import fec
from dsp.synth.bits import FrameSpec, to_bytes
from dsp.synth.chain import Generated, Scene, SignalSpec, generate
from dsp.synth.modulate import map_bits, pulse_shape_offset

NOISE_DB = -20.0
CONV = fec.Convolutional(7, fec.K7)


class Memory:
    def __init__(self, x: Any) -> None:
        self.x = np.asarray(x)
        self.num_samples = len(self.x)

    def read(self, start: int, count: int) -> Any:
        return self.x[start : start + count]


def _scene(modulation: str, esn0_db: float, *, sps: int = 8, seed: int = 5, **kw: Any) -> Generated:
    power = NOISE_DB + esn0_db - 10 * math.log10(sps)
    spec = SignalSpec(modulation=modulation, sps=sps, power_db=power, **kw)
    return generate(Scene(samples=1 << 17, signals=(spec,), noise_db=NOISE_DB), seed)


def test_q_trails_i_by_half_a_symbol() -> None:
    """Rectangular pulses make it exact: I holds symbol k over [8k, 8k + 8), Q from 8k + 4."""
    rng = np.random.default_rng(1)
    symbols = map_bits(rng.integers(0, 2, 2 * 40).astype(np.uint8), "qpsk")
    x = pulse_shape_offset(symbols, 8, "rect", 0.0)
    k = np.arange(2, 38)
    assert np.allclose(x[8 * k + 1].real, symbols[k].real)
    assert np.allclose(x[8 * k + 5].imag, symbols[k].imag)
    assert np.allclose(x[8 * k + 1].imag, symbols[k - 1].imag)  # Q is still on the last symbol
    with pytest.raises(ValueError, match="even"):
        pulse_shape_offset(symbols, 7, "rect", 0.0)


@pytest.mark.parametrize("esn0", [20.0, 8.0])
def test_the_line_pair_in_x_squared_gives_the_rate_and_the_carrier_offset(esn0: float) -> None:
    g = _scene("oqpsk", esn0, offset=0.013)
    x = g.samples * np.exp(-2j * np.pi * 0.010 * np.arange(len(g.samples)))  # leaves 0.003
    found = offset_symbol_rate(x)
    assert found is not None
    assert found.normalised_rate == pytest.approx(1 / 8, rel=1e-4)
    assert found.cfo == pytest.approx(0.003, abs=2e-5)
    assert abs(found.normalised_rate - 1 / 8) < 5 * found.uncertainty + 1e-6


def test_qpsk_shows_no_pair() -> None:
    """Plain QPSK's x² has no lines at all, so there is nothing to mistake for offset QPSK. (A
    structured payload gives x² combs of its own, so the estimator is only run where |x|² shows
    no symbol-rate line, which every other linear modulation has: `analyse` gates on that.)"""
    g = _scene("qpsk", 20.0, offset=0.013, frame=None)
    assert offset_symbol_rate(g.samples) is None


def test_noise_shows_no_pair() -> None:
    rng = np.random.default_rng(0)
    for _ in range(40):
        x = (rng.standard_normal(1 << 15) + 1j * rng.standard_normal(1 << 15)) / math.sqrt(2)
        assert offset_symbol_rate(x) is None


@pytest.mark.parametrize(
    ("esn0", "phase"), [(6.0, 0.0), (10.0, 0.4), (10.0, 1.3), (10.0, 2.9), (8.0, -2.0)]
)
def test_hard_decisions_sit_within_1_db_of_qpsk_theory(esn0: float, phase: float) -> None:
    """The M3 exit gate for this modulation: BER from the recovered symbols against
    Q(sqrt(Es/N0)), taken at the best of the four rotations and a few bit shifts (the pairing of
    I and Q with the symbol is the blind chain's alignment, not this test's subject), at several
    carrier phases: the line of x² that times the signal carries twice the phase."""
    g = _scene("oqpsk", esn0)
    x = g.samples * np.exp(1j * phase - 2j * np.pi * 0.01 * np.arange(len(g.samples)))
    found = offset_symbol_rate(x)
    assert found is not None
    timing = recover_timing(x, found.normalised_rate, 0.35, offset=True, cfo=found.cfo)
    truth = g.signals[0].coded
    best = 1.0
    # Which stream leads is the quarter turn the carrier phase leaves open: one of the two
    # pairings (`symbols`, `alternate`) is the transmitted one, and the chain tries both.
    for symbols in (timing.symbols, timing.alternate):
        carrier = correct_carrier(symbols, 4)
        for rotation in rotations("OQPSK"):
            bits = (demap(rotate(carrier.symbols, rotation), "OQPSK").llr < 0).astype(np.uint8)
            for shift in range(-3, 4):
                a, b = (truth[shift:], bits) if shift >= 0 else (truth, bits[-shift:])
                n = min(len(a), len(b))
                best = min(best, float(np.mean(a[:n] != b[:n])))
    # 1 dB of Es/N0 is a factor of 1.26 in the argument of Q: the BER at esn0 - 1 dB bounds it.
    limit = 0.5 * erfc(sqrt(10 ** ((esn0 - 1) / 10) / 2))
    assert best < limit
    assert best > 0.5 * erfc(sqrt(10 ** ((esn0 + 1) / 10) / 2)) / 3  # and the test isn't vacuous


def _run(spec: SignalSpec, seed: int = 7) -> tuple[Generated, DetectionReport]:
    g = generate(Scene(samples=1 << 18, signals=(spec,), noise_db=NOISE_DB), seed)
    source = Memory(g.samples)
    detections = detect(source, real=False).detections
    assert detections, "the signal must be detected"
    main = max(detections, key=lambda d: (d.stop - d.start) * (d.high - d.low))
    return g, analyse(source, main)


def _spec(esn0: float, **kw: Any) -> SignalSpec:
    power = NOISE_DB + esn0 - 10 * math.log10(8)
    spec = SignalSpec(modulation="oqpsk", sps=8, power_db=power, offset=0.1, **kw)
    return replace(spec, start=10_000, duration=200_000)


@pytest.mark.parametrize(
    ("inner", "offset", "esn0"), [(CONV, 37, 15.0), (None, 0, 18.0)], ids=["coded", "uncoded"]
)
def test_offset_qpsk_decodes_to_the_transmitted_frames(
    inner: fec.Convolutional | None, offset: int, esn0: float
) -> None:
    g, report = _run(_spec(esn0, inner=inner, stream_offset=offset))
    assert report.level is EvidenceLevel.VERIFIED
    assert report.label == "OQPSK"
    spec = FrameSpec()
    rows = g.signals[0].framed.reshape(-1, spec.length)
    truth = [to_bytes(r[len(spec.sync_bits) : -16]).hex().upper() for r in rows]
    passing = [f for f in report.frames if f.crc == "pass"]
    assert len(passing) >= 10
    assert all(f.payload_hex in truth for f in passing)
    classify = next(s for s in report.stages if s.id == "classify")
    assert classify.parameters[0].value == "OQPSK"
    assert classify.parameters[0].level is EvidenceLevel.VERIFIED
    estimate = next(s for s in report.stages if s.id == "estimate")
    rate = next(p for p in estimate.parameters if p.id == "symbol_rate")
    assert rate.value == pytest.approx(1 / 8, rel=1e-3)
    assert "x²" in rate.method  # it says where the rate came from
    carrier = next(p for p in estimate.parameters if p.id == "carrier")
    assert carrier.value == pytest.approx(0.1, abs=1e-3)
    assert report.eye is None  # no eye for offset QPSK: its I and Q open half a symbol apart
    assert report.search is not None
    assert report.search.shuffled_runs > 0 and report.search.shuffled_accepts == 0


def test_an_undecodable_offset_qpsk_burst_is_still_called_offset_qpsk_not_am() -> None:
    """Without the pair check a burst with no |x|² line goes to the analog test and reads as AM;
    with it, a failed decode is reported as OQPSK? (a hypothesis), never VERIFIED."""
    g, report = _run(replace(_spec(4.0), frame=None))
    assert g.signals[0].coded.size
    assert report.kind != "analog"
    assert report.level is not EvidenceLevel.VERIFIED
    assert report.label == "OQPSK?"
