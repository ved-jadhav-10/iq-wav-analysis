"""Outer-code and interleaver modules (PLAN M5): exact ground-truth round trips against
dsp.synth's own encoders - RS(255,223) via galois, and the block-interleaver catalogue."""

import numpy as np
import pytest

from dsp.deinterleave import (
    CATALOGUE,
    FORNEY_CATALOGUE,
    Block,
    Forney,
    Helical,
    Interleaver,
    Qpp,
    Wifi,
    deinterleave,
    deinterleave_forney,
)
from dsp.fec.rs import (
    CCSDS_FIELD_POLY,
    CCSDS_FIRST_ROOT,
    CCSDS_ROOT_POWER,
    decode_block,
    scan_interleave_depths,
)
from dsp.synth import interleave as il
from dsp.synth.fec import RS_CCSDS, RS_DVB


def test_rs_ccsds_corrects_up_to_t_and_fails_beyond_it() -> None:
    rng = np.random.default_rng(11)
    message = rng.integers(0, 256, 223, dtype=np.uint8).tobytes()
    codeword = RS_CCSDS.encode(message)
    assert len(codeword) == 255

    t = (255 - 223) // 2
    bad = bytearray(codeword)
    for i in rng.choice(255, t, replace=False):
        bad[i] ^= 0xFF
    out = decode_block(bytes(bad))
    assert out is not None
    decoded, n_corrected = out
    assert decoded == message
    assert n_corrected == t

    too_many = bytearray(codeword)
    for i in rng.choice(255, t + 1, replace=False):
        too_many[i] ^= 0xFF
    assert decode_block(bytes(too_many)) is None


def test_rs_dvb_shortened_code_round_trips() -> None:
    """A shortened code (n < 255, DVB's RS(204, 188)) exercises the same left-zero-pad
    reconstruction as CCSDS, just with different field parameters."""
    rng = np.random.default_rng(12)
    message = rng.integers(0, 256, 188, dtype=np.uint8).tobytes()
    codeword = RS_DVB.encode(message)
    assert len(codeword) == 204

    t = (204 - 188) // 2
    bad = bytearray(codeword)
    for i in rng.choice(204, t, replace=False):
        bad[i] ^= 0xFF
    out = decode_block(bytes(bad), n=204, k=188, field_poly=0x11D, first_root=0, root_power=1)
    assert out is not None
    assert out == (message, t)


def test_decode_block_rejects_the_wrong_length() -> None:
    with pytest.raises(ValueError, match="expected 255"):
        decode_block(b"\x00" * 10)


def _synth_twin(entry: Interleaver) -> il.BlockInterleaver:
    """The generator's own interleaver for a catalogue entry."""
    if isinstance(entry, Block):
        return il.Block(entry.rows, entry.cols)
    if isinstance(entry, Helical):
        return il.Helical(entry.rows, entry.cols)
    if isinstance(entry, Qpp):
        return il.Qpp(entry.k, entry.f1, entry.f2)
    return il.Wifi(entry.n_cbps, entry.n_bpsc)


def test_the_catalogue_holds_every_family_and_no_duplicates() -> None:
    kinds = {type(e) for e in CATALOGUE}
    assert kinds == {Block, Helical, Wifi, Qpp}
    assert len({e.label for e in CATALOGUE}) == len(CATALOGUE)
    assert [e.n_cbps for e in CATALOGUE if isinstance(e, Wifi)] == [48, 96, 192, 288]


@pytest.mark.parametrize("entry", CATALOGUE, ids=lambda e: e.label)
def test_catalogue_entry_inverts_synths_interleaver_exactly(entry: Interleaver) -> None:
    rng = np.random.default_rng(entry.size)
    blocks = 5
    x = rng.integers(0, 2, blocks * entry.size, dtype=np.uint8)
    synth_entry = _synth_twin(entry)
    # The same permutation, not merely one that round-trips with itself.
    assert np.array_equal(entry.permutation(), synth_entry.permutation())
    interleaved = il.interleave(x, synth_entry)
    recovered = deinterleave(interleaved, entry)
    assert np.array_equal(recovered, x)
    assert np.array_equal(recovered, il.deinterleave(interleaved, synth_entry))


@pytest.mark.parametrize("entry", FORNEY_CATALOGUE, ids=lambda e: e.label)
def test_forney_entry_inverts_synths_interleaver_after_its_lag(entry: Forney) -> None:
    rng = np.random.default_rng(entry.branches * 100 + entry.step)
    x = rng.integers(0, 2, 600, dtype=np.uint8)
    interleaved = il.Convolutional(entry.branches, entry.step).interleave(x)
    recovered = deinterleave_forney(interleaved, entry)
    assert np.array_equal(recovered[entry.lag :], x[: len(x) - entry.lag])
    assert not recovered[: entry.lag].any() or entry.lag == 0  # start-up filler is zeros
    assert len({(e.branches, e.step) for e in FORNEY_CATALOGUE}) == len(FORNEY_CATALOGUE)


def test_forney_phase_drops_leading_elements_so_the_lanes_line_up_again() -> None:
    entry = Forney(4, 3)
    x = np.random.default_rng(3).integers(0, 2, 400, dtype=np.uint8)
    interleaved = il.Convolutional(4, 3).interleave(x)
    junk = np.array([1, 0, 1], dtype=np.uint8)
    recovered = deinterleave_forney(np.concatenate([junk, interleaved]), entry, phase=3)
    assert np.array_equal(recovered[entry.lag :], x[: len(x) - entry.lag])


def test_qpp_table_entries_are_permutations_with_the_documented_form() -> None:
    from math import gcd

    for e in (e for e in CATALOGUE if isinstance(e, Qpp)):
        assert sorted(e.permutation()) == list(range(e.k))  # raises if it isn't
        assert gcd(e.f1, e.k) == 1  # a QPP needs f1 coprime with K, and f2 built from K's primes
    assert Qpp(40, 3, 10).permutation()[:4].tolist() == [0, 13, 46 % 40, (3 * 3 + 10 * 9) % 40]


def test_deinterleave_drops_a_leading_alignment_and_a_trailing_partial_block() -> None:
    entry = Block(4, 6)
    rng = np.random.default_rng(4)
    x = rng.integers(0, 2, 3 * entry.size, dtype=np.uint8)
    synth_entry = il.Block(entry.rows, entry.cols)
    interleaved = il.interleave(x, synth_entry)
    junk_prefix = rng.integers(0, 2, 5, dtype=np.uint8)
    junk_suffix = rng.integers(0, 2, 7, dtype=np.uint8)
    stream = np.concatenate([junk_prefix, interleaved, junk_suffix])
    recovered = deinterleave(stream, entry, alignment=len(junk_prefix))
    # Only whole blocks come back; the trailing partial block (junk_suffix) is dropped.
    whole = (len(interleaved) // entry.size) * entry.size
    assert np.array_equal(recovered, x[:whole])


def test_scan_interleave_depths_finds_the_true_depth() -> None:
    depth = 3
    rng = np.random.default_rng(21)
    messages = [rng.integers(0, 256, 223, dtype=np.uint8).tobytes() for _ in range(depth)]
    codewords = np.concatenate([np.frombuffer(RS_CCSDS.encode(m), np.uint8) for m in messages])
    stream = il.interleave(codewords, il.Block(depth, 255)).tobytes()

    attempts = scan_interleave_depths(stream)
    assert [a.depth for a in attempts] == [1, 2, 3, 4, 5]
    by_depth = {a.depth: a for a in attempts}
    assert by_depth[depth].ok
    assert by_depth[depth].messages == tuple(messages)
    assert all(c == 0 for c in by_depth[depth].corrected)
    # No other depth in the default range should also happen to decode clean.
    assert sum(a.ok for a in attempts) == 1


def test_scan_interleave_depths_reports_a_failed_attempt_for_short_input() -> None:
    # 100 bytes is too short even for depth 1 (needs 255): every depth in the default range is
    # tried and reported as a failed attempt, not silently skipped.
    attempts = scan_interleave_depths(b"\x00" * 100)
    assert [a.depth for a in attempts] == [1, 2, 3, 4, 5]
    assert all(not a.ok and a.messages == () for a in attempts)


def test_ccsds_defaults_match_synths_rs_ccsds() -> None:
    assert (
        RS_CCSDS.field_poly,
        RS_CCSDS.first_root,
        RS_CCSDS.root_power,
    ) == (CCSDS_FIELD_POLY, CCSDS_FIRST_ROOT, CCSDS_ROOT_POWER)
