"""Es/N0 from three estimators (PLAN M2): the value and its evidence against the synth's truth."""

import contextlib
import math
from dataclasses import replace
from typing import Any

import numpy as np
import pytest

from dsp.analyse import analyse
from dsp.detect import detect
from dsp.estimate.params import snr_m2m4, snr_psd
from dsp.evidence import EvidenceLevel, Parameter
from dsp.synth.chain import Scene, SignalSpec, generate

NOISE_DB = -20.0


class Memory:
    def __init__(self, x: Any) -> None:
        self.x = np.asarray(x)
        self.num_samples = len(self.x)

    def read(self, start: int, count: int) -> Any:
        return self.x[start : start + count]


def _esn0(modulation: str, truth_db: float) -> Parameter:
    power = NOISE_DB + truth_db - 10 * math.log10(8)
    spec = replace(
        SignalSpec(modulation=modulation, sps=8, power_db=power, offset=0.1, frame=None),
        start=10_000,
        duration=200_000,
    )
    g = generate(Scene(samples=1 << 18, signals=(spec,), noise_db=NOISE_DB), 3)
    source = Memory(g.samples)
    detections = detect(source, real=False).detections
    main = max(detections, key=lambda d: (d.stop - d.start) * (d.high - d.low))
    report = analyse(source, main)
    estimate = next(s for s in report.stages if s.id == "estimate")
    return next(p for p in estimate.parameters if p.id == "esn0")


@pytest.mark.parametrize(
    ("modulation", "truth"),
    [("qpsk", 4.0), ("qpsk", 8.0), ("qpsk", 20.0), ("16qam", 12.0)],  # each a full chain run
)
def test_esn0_is_within_a_dB_of_the_truth_from_4_to_20_dB(modulation: str, truth: float) -> None:
    p = _esn0(modulation, truth)
    assert p.level is EvidenceLevel.ESTIMATED and p.uncertainty is not None
    assert float(p.value or 0) == pytest.approx(truth, abs=1.0)
    assert "PSD moments" in p.method
    assert any(line.startswith("M2M4:") for line in p.evidence)
    assert any(line.startswith("EVM:") for line in p.evidence)


def test_the_estimators_agree_where_they_are_trusted_and_it_says_so() -> None:
    p = _esn0("qpsk", 12.0)
    assert p.confidence is not None and p.confidence > 0.5  # agreement within a dB
    assert any("agree to within" in line for line in p.evidence)


def test_an_estimator_outside_its_range_is_listed_but_not_counted() -> None:
    p = _esn0("qpsk", 4.0)  # EVM reads low below about 8 dB
    evm = next(line for line in p.evidence if line.startswith("EVM:"))
    assert "outside its trusted range" in evm


def test_psd_moments_read_the_snr_in_the_signals_own_bandwidth_down_to_0_db() -> None:
    sps, esn0 = 8.0, 0.0
    spec = SignalSpec("qpsk", sps=sps, frame=None, offset=0.0, power_db=0.0)
    scene = Scene(1 << 17, (spec,), noise_db=-esn0 + 10 * math.log10(sps))
    g = generate(scene, seed=5)
    est = snr_psd(g.samples, 4096)
    rate = 1 / sps
    assert 10 * math.log10(est.signal_power / (est.noise_density * rate)) == pytest.approx(
        esn0, abs=0.5
    )
    # its noise-equivalent bandwidth: the symbol rate over (1 - rolloff / 4) for an RRC pulse
    assert est.bandwidth == pytest.approx(rate / (1 - 0.35 / 4), rel=0.05)


def test_noise_alone_gives_no_snr() -> None:
    rng = np.random.default_rng(0)
    x = rng.standard_normal(1 << 16) + 1j * rng.standard_normal(1 << 16)
    # Noise has no spectral structure to measure: power or spread comes out at the scatter, so
    # either nothing is returned or the SNR is far below any signal's.
    with contextlib.suppress(ValueError):
        assert snr_psd(x).snr_db < -3.0


def test_m2m4_recovers_qpsk_and_16qam_symbol_snr() -> None:
    rng = np.random.default_rng(1)
    n = 200_000
    for kurtosis, symbols in (
        (1.0, np.exp(1j * (np.pi / 4 + np.pi / 2 * rng.integers(0, 4, n)))),
        (
            1.32,
            (rng.choice([-3, -1, 1, 3], n) + 1j * rng.choice([-3, -1, 1, 3], n)) / math.sqrt(10),
        ),
    ):
        for snr in (6.0, 12.0):
            noise = (rng.standard_normal(n) + 1j * rng.standard_normal(n)) * math.sqrt(
                10 ** (-snr / 10) / 2
            )
            received: Any = symbols + noise
            assert snr_m2m4(np.asarray(received, np.complex128), kurtosis) == pytest.approx(
                snr, abs=0.4
            )
    assert snr_m2m4(np.ones(100, np.complex128)) is None  # too few symbols
