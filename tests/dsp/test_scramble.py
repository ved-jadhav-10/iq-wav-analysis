"""Descramblers against the generator's own scramblers (PLAN M6): two implementations of each,
so a shared misreading of the standard would still show up in the sequences."""

import numpy as np
import pytest

from dsp.scramble import CCSDS, DESCRAMBLERS, G3RUH
from dsp.synth.bits import SCRAMBLERS, Scrambler, SelfSyncScrambler, to_bytes


def test_the_ccsds_sequence_starts_ff_48_0e_c0_and_has_period_255() -> None:
    seq = CCSDS.sequence(255 * 2)
    assert to_bytes(seq[:64]).hex() == "ff480ec09a0d70bc"
    assert np.array_equal(seq[:255], seq[255:])


def test_the_ccsds_sequence_matches_the_generators() -> None:
    synth = SCRAMBLERS["CCSDS"]
    assert isinstance(synth, Scrambler)
    assert np.array_equal(CCSDS.sequence(1000), synth.sequence(1000))


def test_an_additive_descrambler_undoes_the_generators_scrambler_per_frame() -> None:
    synth = SCRAMBLERS["CCSDS"]
    data = np.random.default_rng(1).integers(0, 2, 500, dtype=np.uint8)
    assert np.array_equal(CCSDS.frame(synth.apply(data)), data)


def test_the_g3ruh_descrambler_undoes_the_generators_scrambler_after_its_first_17_bits() -> None:
    synth = SCRAMBLERS["G3RUH"]
    assert isinstance(synth, SelfSyncScrambler)
    data = np.random.default_rng(2).integers(0, 2, 2000, dtype=np.uint8)
    scrambled = synth.apply(data)
    assert not np.array_equal(scrambled, data)
    assert np.array_equal(G3RUH.stream(scrambled), data)  # from the start: it began at zero
    # Started in the middle it needs 17 bits of history, then it is exact.
    assert np.array_equal(G3RUH.stream(scrambled[500:])[17:], data[517:])


def test_a_self_synchronising_scrambler_turns_one_error_into_three() -> None:
    synth = SCRAMBLERS["G3RUH"]
    data = np.zeros(500, np.uint8)
    scrambled = synth.apply(data)
    scrambled[300] ^= 1
    errors = np.flatnonzero(G3RUH.stream(scrambled))
    assert list(errors) == [300, 312, 317]


def test_each_kind_refuses_the_other_kinds_call() -> None:
    with pytest.raises(ValueError, match="whole stream"):
        G3RUH.frame(np.zeros(10, np.uint8))
    with pytest.raises(ValueError, match="use `frame`"):
        CCSDS.stream(np.zeros(10, np.uint8))
    assert {d.kind for d in DESCRAMBLERS} == {"additive", "self-sync"}
