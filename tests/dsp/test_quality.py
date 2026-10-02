"""Capture quality (PLAN M2): each check against a recording built with a known fault."""

import math
from typing import Any

import numpy as np
import pytest

from dsp import quality
from dsp.evidence import EvidenceLevel, Parameter
from dsp.quality import capture_quality


class Memory:
    def __init__(self, x: Any) -> None:
        self.x = np.asarray(x)
        self.num_samples = len(self.x)

    def read(self, start: int, count: int) -> Any:
        return self.x[start : start + count]


def noise(n: int, seed: int = 0, sigma: float = 1.0) -> Any:
    rng = np.random.default_rng(seed)
    return sigma * (rng.standard_normal(n) + 1j * rng.standard_normal(n))


def by_id(x: Any) -> dict[str, Parameter]:
    return {p.id: p for p in capture_quality(Memory(x))}


def test_clean_noise_has_nothing_to_report() -> None:
    p = by_id(noise(1 << 19))
    assert p["clipping"].value == 0
    assert not p["clipping"].warnings
    assert p["gaps"].value == 0 and not p["gaps"].warnings
    assert isinstance(p["dc_offset"].value, float) and p["dc_offset"].value < -40
    for name in ("iq_gain_imbalance", "iq_phase_imbalance"):
        assert p[name].level is EvidenceLevel.ESTIMATED
        sigma = p[name].uncertainty
        assert sigma is not None
        assert abs(float(p[name].value or 0)) < 4 * sigma + 0.01
        assert not p[name].warnings


def test_clipping_is_the_share_of_components_at_the_plateau() -> None:
    x = noise(1 << 18)
    ceiling = 1.5
    x = np.clip(x.real, -ceiling, ceiling) + 1j * np.clip(x.imag, -ceiling, ceiling)
    comps = np.concatenate([x.real, x.imag])
    expected = 100 * float(np.mean(np.abs(comps) == ceiling))
    clipping = by_id(x)["clipping"]
    assert clipping.value == pytest.approx(expected, rel=1e-9)
    assert expected > 5  # the case is real
    assert clipping.warnings and "saturated" in clipping.warnings[0]
    assert clipping.level is EvidenceLevel.MEASURED


def test_a_peak_touched_once_is_not_clipping() -> None:
    x = noise(1 << 16)
    x[100] = 9 + 0j  # one tall sample
    assert by_id(x)["clipping"].value == 0


def test_dc_offset_is_the_power_of_the_mean_over_the_total_power() -> None:
    a, b, sigma = 0.3, 0.1, 1.0
    x = noise(1 << 19, sigma=sigma) + (a + 1j * b)
    total = 2 * sigma**2 + a * a + b * b  # E|x|^2: I and Q each carry sigma^2
    truth = 10 * math.log10((a * a + b * b) / total)
    assert by_id(x)["dc_offset"].value == pytest.approx(truth, abs=0.1)


def test_gain_and_phase_imbalance_are_recovered() -> None:
    n = 1 << 20
    rng = np.random.default_rng(3)
    i, q = rng.standard_normal(n), rng.standard_normal(n)
    gain_db, phase_deg = 1.5, 5.0
    amplitude = 10 ** (-gain_db / 20)  # Q weaker by gain_db: I over Q = +gain_db
    phi = math.radians(phase_deg)
    x = i + 1j * amplitude * (q * math.cos(phi) + i * math.sin(phi))
    p = by_id(x)
    gain, phase = p["iq_gain_imbalance"], p["iq_phase_imbalance"]
    # The Q branch carries `i sin(phi)` as well, which adds to its power by sin²(phi) (0.8 %).
    q_power = amplitude**2 * (math.cos(phi) ** 2 + math.sin(phi) ** 2)
    truth_gain = 10 * math.log10(1 / q_power)
    truth_phase = math.degrees(math.asin(amplitude * math.sin(phi) / math.sqrt(q_power)))
    assert float(gain.value or 0) == pytest.approx(truth_gain, abs=3 * float(gain.uncertainty or 0))
    assert float(phase.value or 0) == pytest.approx(
        truth_phase, abs=3 * float(phase.uncertainty or 0)
    )
    assert gain.warnings and phase.warnings  # both over their warning limits


def test_a_real_recording_has_no_iq_imbalance_to_report() -> None:
    p = by_id(noise(1 << 17).real)
    assert "iq_gain_imbalance" not in p and "iq_phase_imbalance" not in p
    assert p["clipping"].level is EvidenceLevel.MEASURED


def test_gaps_are_runs_of_repeated_samples_across_chunk_joins() -> None:
    n = (1 << 19) + 5000
    x = noise(n)
    join = quality.CHUNK
    x[100:200] = 0  # 100 samples
    x[join - 40 : join + 60] = 0.25 + 0.25j  # 100 samples spanning two chunks, not zeros
    x[5000:5031] = 0  # 31: one short of a gap
    x[n - 70 :] = 0  # a run that ends the recording
    p = by_id(x)["gaps"]
    assert p.value == 3
    assert "270 samples in all" in p.evidence[0]
    assert "first at sample 100" in p.evidence[0]
    assert p.warnings


@pytest.mark.parametrize(
    ("start", "stop"),
    [
        (quality.CHUNK - 100, quality.CHUNK),  # ends exactly at the join
        (quality.CHUNK, quality.CHUNK + 100),  # starts exactly at the join
        (10, 3 * quality.CHUNK),  # a hold over three chunks, ending exactly at a join
        (quality.CHUNK - 31, quality.CHUNK + 1),  # 32 samples, one more than the short run
    ],
)
def test_a_gap_is_counted_whatever_the_join_does_to_it(start: int, stop: int) -> None:
    x = noise(4 * quality.CHUNK)
    x[start:stop] = 0.5
    p = by_id(x)["gaps"]
    assert p.value == 1
    assert f"{stop - start:,} samples in all, the first at sample {start:,}" in p.evidence[0]


def test_a_gap_just_short_of_the_minimum_is_not_counted_at_a_join() -> None:
    x = noise(2 * quality.CHUNK)
    x[quality.CHUNK - 31 : quality.CHUNK] = 0.5  # 31 samples, ending at the join
    assert by_id(x)["gaps"].value == 0


def test_a_gap_that_starts_a_recording_is_counted() -> None:
    x = noise(1 << 16)
    x[:64] = 0
    p = by_id(x)["gaps"]
    assert p.value == 1 and "first at sample 0" in p.evidence[0]


def test_a_long_recording_is_read_in_pieces_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(quality, "FULL_SCAN", 1 << 17)
    monkeypatch.setattr(quality, "PIECES", 4)
    monkeypatch.setattr(quality, "PIECE", 1 << 16)
    x = noise(1 << 19)
    p = by_id(x)
    assert "evenly spaced pieces" in p["clipping"].evidence[0]
    assert "of 524,288 samples" in p["clipping"].evidence[0]


def test_a_gap_in_a_sampled_scan_is_placed_where_it_is(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(quality, "FULL_SCAN", 1 << 17)
    monkeypatch.setattr(quality, "PIECES", 4)
    monkeypatch.setattr(quality, "PIECE", 1 << 16)
    n = 1 << 19
    x = noise(n)
    starts = [round(i * (n - (1 << 16)) / 3) for i in range(4)]  # where the pieces are read
    at = starts[1] + 1000
    x[at : at + 100] = 0
    p = by_id(x)["gaps"]
    assert p.value == 1
    assert f"the first at sample {at:,}" in p.evidence[0]


def _eight_bit(x: Any, scale: float) -> Any:
    """x scaled and rounded to integer levels, as an 8-bit capture would hold it."""
    return np.round(x.real * scale) + 1j * np.round(x.imag * scale)


def test_a_quantised_constant_envelope_signal_is_not_clipping() -> None:
    n = np.arange(1 << 18)
    tone = np.exp(2j * np.pi * 0.013 * n) + 0.001 * noise(len(n))
    clipping = by_id(_eight_bit(tone, 127.0))["clipping"]
    assert clipping.value == 0 and not clipping.warnings
    assert "no plateau" in clipping.evidence[0]


def test_a_quantised_signal_that_hits_the_rail_is_clipping() -> None:
    x = _eight_bit(noise(1 << 18, sigma=60), 1.0)
    x = np.clip(x.real, -127, 127) + 1j * np.clip(x.imag, -127, 127)
    clipping = by_id(x)["clipping"]
    assert float(clipping.value or 0) > 2  # sigma 60 clipped at 127: about 3.5 % of components
    assert clipping.warnings and "a plateau" in clipping.evidence[0]


def test_a_signal_with_one_level_has_no_plateau_to_find() -> None:
    rng = np.random.default_rng(2)
    x = rng.choice([-1.0, 1.0], 1 << 16) + 1j * rng.choice([-1.0, 1.0], 1 << 16)  # QPSK, no noise
    clipping = by_id(x)["clipping"]
    assert clipping.value == 0 and "no other level" in clipping.evidence[0]


def test_a_file_shorter_than_one_block_still_gets_iq_imbalance_and_says_how() -> None:
    p = by_id(noise(30_000))
    for name in ("iq_gain_imbalance", "iq_phase_imbalance"):
        assert p[name].uncertainty is not None
        assert "fewer than one block" in p[name].evidence[0]
        assert "independent samples" in p[name].evidence[0]


def test_an_empty_recording_is_unknown() -> None:
    (p,) = capture_quality(Memory(np.zeros(0, np.complex64)))
    assert p.level is EvidenceLevel.UNKNOWN and p.resolve_hint


def test_the_same_recording_gives_the_same_parameters() -> None:
    x = noise(1 << 18, seed=9)
    assert capture_quality(Memory(x)) == capture_quality(Memory(x))
