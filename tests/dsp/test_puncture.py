"""Depuncturing against the synth encoder's puncturing, and decoding through it (PLAN M5)."""

import numpy as np
import pytest

from dsp.fec.puncture import PUNCTURES, Puncture, depuncture
from dsp.fec.viterbi import K7_R12, decode
from dsp.synth import fec

MOTHER = fec.Convolutional(7, fec.K7)


def llr_of(bits: np.ndarray, sigma: float = 0.0, seed: int = 0) -> np.ndarray:
    x = 1.0 - 2.0 * bits.astype(np.float64)
    if sigma:
        x = x + np.random.default_rng(seed).normal(0, sigma, len(x))
    return 2 * x / max(sigma, 0.5) ** 2


def test_the_catalogue_matches_the_synth_patterns_and_rates() -> None:
    assert {p.rate for p in PUNCTURES} == set(fec.PUNCTURES)
    for p in PUNCTURES:
        assert p.pattern == fec.PUNCTURES[p.rate]
        assert fec.Convolutional(7, fec.K7, p.pattern).rate == tuple(map(int, p.rate.split("/")))
    assert [p.kept for p in PUNCTURES] == [3, 4, 6, 8]


@pytest.mark.parametrize("puncture", PUNCTURES, ids=lambda p: p.rate)
def test_depuncture_puts_each_bit_back_where_the_mother_code_had_it(puncture: Puncture) -> None:
    u = np.random.default_rng(1).integers(0, 2, 200, dtype=np.uint8)
    mother = MOTHER.encode(u)
    sent = fec.Convolutional(7, fec.K7, puncture.pattern).encode(u)
    out = depuncture(llr_of(sent), puncture, 0)
    seen = out != 0
    assert 0 < seen.sum() == len(sent)
    assert np.array_equal((out[seen] < 0).astype(np.uint8), mother[: len(out)][seen])
    assert len(out) % 2 == 0


@pytest.mark.parametrize("puncture", PUNCTURES, ids=lambda p: p.rate)
def test_every_phase_lands_on_the_same_positions_as_the_stream_it_was_cut_from(
    puncture: Puncture,
) -> None:
    u = np.random.default_rng(2).integers(0, 2, 300, dtype=np.uint8)
    sent = llr_of(fec.Convolutional(7, fec.K7, puncture.pattern).encode(u))
    whole = depuncture(sent, puncture, 0)
    for phase in range(puncture.kept):
        cut = depuncture(sent[phase:], puncture, phase)
        assert np.array_equal(cut, whole[: len(cut)] * (np.cumsum(whole != 0)[: len(cut)] > phase))


@pytest.mark.parametrize("puncture", PUNCTURES, ids=lambda p: p.rate)
@pytest.mark.parametrize("phase", [0, 1, 2])
def test_viterbi_decodes_a_punctured_stream_started_mid_period(
    puncture: Puncture, phase: int
) -> None:
    """Noise-free and lightly noisy: the message comes back (past the start-up) when the phase is
    right, and not when it is wrong."""
    u = np.random.default_rng(3).integers(0, 2, 2000, dtype=np.uint8)
    sent = fec.Convolutional(7, fec.K7, puncture.pattern).encode(u)
    received = llr_of(sent, sigma=0.4, seed=4)
    good = decode(depuncture(received[phase:], puncture, phase), K7_R12)
    # Depuncturing starts on the period boundary, so message bit i is still bit i.
    errors = good[100 : len(good) - 100] != u[100 : len(good) - 100]
    assert errors.mean() < 0.02
    wrong = decode(depuncture(received[phase:], puncture, (phase + 1) % puncture.kept), K7_R12)
    assert (wrong[100 : len(wrong) - 100] != u[100 : len(wrong) - 100]).mean() > 0.2


def test_a_phase_outside_the_pattern_is_refused() -> None:
    with pytest.raises(ValueError, match="phase"):
        depuncture(np.ones(10), PUNCTURES[0], PUNCTURES[0].kept)
    assert len(depuncture(np.zeros(0), PUNCTURES[0], 0)) == 0


def test_the_punctured_code_is_the_mother_code_labelled_with_its_rate() -> None:
    code = PUNCTURES[1].code()
    assert (code.constraint, code.generators) == (7, (0o171, 0o133))
    assert "r3/4 punctured" in code.name
