"""Blind sync, frame length, header fields and CRC recovery against exact ground truth from
`dsp.synth.bits` (PLAN M6)."""

import numpy as np
import pytest
from numpy.typing import NDArray

from dsp.blind_framing import (
    analyse_stream,
    discover_sync,
    header_fields,
    recover_crc,
)
from dsp.gf2.poly import pgcd, plcm, pmod, pmul
from dsp.synth.bits import CRCS, SYNC_WORDS, FrameSpec, frames, int_bits


def make(
    spec: FrameSpec, n_frames: int, seed: int = 1, drop: int = 0
) -> tuple[NDArray[np.uint8], NDArray[np.uint8]]:
    rng = np.random.default_rng(seed)
    payloads = rng.integers(0, 256, (n_frames, spec.payload_bytes), dtype=np.uint8)
    return frames(spec, payloads)[drop:], payloads


def flip(bits: NDArray[np.uint8], rate: float, seed: int = 2) -> NDArray[np.uint8]:
    return bits ^ (np.random.default_rng(seed).random(len(bits)) < rate).astype(np.uint8)


def sync_bits(name: str) -> NDArray[np.uint8]:
    value, width = SYNC_WORDS[name]
    return int_bits(value, width)


@pytest.mark.parametrize("sync", ["CCSDS ASM", "POCSAG", "Barker-13"])
@pytest.mark.parametrize("drop", [0, 37])
def test_a_clean_stream_gives_the_sync_word_length_and_position(sync: str, drop: int) -> None:
    spec = FrameSpec(sync=sync, payload_bytes=64 if sync != "Barker-13" else 24)
    bits, _ = make(spec, 140, drop=drop)
    found = discover_sync(bits)
    assert found is not None and found.verified
    assert found.period == spec.length
    # The constant prefix: the sync word, less any trailing run of one value that the counter's
    # unused high bits would extend anyway (POCSAG's word ends 000).
    true = sync_bits(sync)
    assert np.array_equal(found.word, true[: len(found.word)]) and len(found.word) >= len(true) - 4
    # The first sync word in the (cut) stream starts at the first frame boundary at or after it.
    assert found.start % spec.length == (-drop) % spec.length
    assert found.hits == found.heldout > 30
    assert found.p_value < found.threshold and found.variant == "plain"


def test_bit_errors_do_not_hide_the_sync_word() -> None:
    spec = FrameSpec()
    bits, _ = make(spec, 160)
    found = discover_sync(flip(bits, 0.005))
    assert found is not None and found.verified and found.period == spec.length
    assert np.array_equal(found.word, sync_bits("CCSDS ASM"))
    assert found.hits >= 0.9 * found.heldout


def test_an_inverted_stream_gives_the_complemented_word() -> None:
    spec = FrameSpec()
    bits, _ = make(spec, 140)
    found = discover_sync(1 - bits)
    assert found is not None and found.verified and found.period == spec.length
    assert np.array_equal(found.word, 1 - sync_bits("CCSDS ASM"))


def test_an_nrzi_stream_is_found_in_its_differenced_form() -> None:
    spec = FrameSpec()
    bits, _ = make(spec, 140)
    encoded = np.cumsum(bits, dtype=np.int64).astype(np.uint8) % 2  # NRZ-I: a 1 toggles
    found = discover_sync(encoded)
    assert found is not None and found.verified
    assert found.variant == "nrzi" and found.period == spec.length
    assert np.array_equal(found.word, sync_bits("CCSDS ASM"))


@pytest.mark.parametrize("seed", range(6))
def test_structureless_streams_have_no_sync_word(seed: int) -> None:
    """Null controls: random bits, all zeros, and real frames with their bits shuffled."""
    rng = np.random.default_rng(seed)
    bits, _ = make(FrameSpec(), 140, seed=seed)
    assert discover_sync(rng.integers(0, 2, 80_000, dtype=np.uint8)) is None
    assert discover_sync(np.zeros(80_000, np.uint8)) is None
    assert discover_sync(rng.permutation(bits)) is None


def test_a_stream_too_short_for_the_row_rule_gives_none() -> None:
    bits, _ = make(FrameSpec(), 4)
    assert discover_sync(bits) is None


def test_the_held_out_recurrence_is_what_verifies_it() -> None:
    """Discovery reads the first half of the rows, and the second half counts on its own, so a
    stream whose second half has no frames is not verified."""
    spec = FrameSpec()
    good, _ = make(spec, 140)
    rng = np.random.default_rng(9)
    # First half framed, second half noise: discovery finds the frames, the held-out half
    # cannot confirm them.
    half = np.concatenate(
        [good[: 70 * spec.length], rng.integers(0, 2, 70 * spec.length, dtype=np.uint8)]
    )
    found = discover_sync(half)
    assert found is None or not found.verified


# --- header fields -------------------------------------------------------------------------


def test_the_header_is_sync_then_a_counter_then_payload() -> None:
    spec = FrameSpec()
    bits, _ = make(spec, 140)
    found = discover_sync(bits)
    assert found is not None
    fields = header_fields(found.frames(), len(found.word))
    kinds = [(f.kind, f.start, f.width) for f in fields]
    assert kinds == [("sync", 0, 32), ("counter", 32, 16), ("variable", 48, 8)]
    assert fields[1].step == 1 and fields[1].p_value is not None and fields[1].p_value < 1e-9


def test_a_constant_header_byte_and_a_counter_step_are_read_exactly() -> None:
    rng = np.random.default_rng(3)
    sync = sync_bits("POCSAG")
    rows = []
    for i in range(120):
        counter = (7 + 3 * i) % 256
        rows.append(
            np.concatenate(
                [
                    sync,
                    int_bits(0xA5, 8),
                    int_bits(counter, 8),
                    rng.integers(0, 2, 200, dtype=np.uint8),
                ]
            )
        )
    found = discover_sync(np.concatenate(rows))
    assert found is not None and found.period == len(rows[0])
    fields = header_fields(found.frames(), len(found.word))
    # Sync and a constant header byte are both constant columns: one constant prefix of 40 bits.
    assert (fields[0].kind, fields[0].width) == ("sync", 40)
    assert np.array_equal(found.word, np.concatenate([sync, int_bits(0xA5, 8)]))
    assert (fields[1].kind, fields[1].width, fields[1].step) == ("counter", 8, 3)


def test_random_bytes_are_not_called_constant_or_counters() -> None:
    rng = np.random.default_rng(4)
    rows = np.hstack(
        [np.tile(sync_bits("CCSDS ASM"), (100, 1)), rng.integers(0, 2, (100, 300), dtype=np.uint8)]
    )
    fields = header_fields(rows, 32)
    assert [f.kind for f in fields] == ["sync", "variable"]


# --- CRC -----------------------------------------------------------------------------------


@pytest.mark.parametrize("crc", list(CRCS))
def test_the_crc_is_recovered_blind_with_its_name_and_passes_on_held_out_frames(crc: str) -> None:
    spec = FrameSpec(crc=crc, payload_bytes=40)
    bits, _ = make(spec, 100, seed=5)
    found = analyse_stream(bits)
    assert found is not None and found.sync.verified and found.sync.period == spec.length
    fit = found.crc
    assert fit is not None
    truth = CRCS[crc]
    assert (fit.width, fit.poly, fit.refin, fit.refout) == (
        truth.width,
        truth.poly,
        truth.refin,
        truth.refout,
    )
    assert fit.name == crc  # the catalogue entry with this init and final XOR
    assert fit.passes == fit.heldout and fit.p_value < fit.threshold
    body = found.frames[:, 32:]
    assert all(fit.check(row) for row in body)
    assert not fit.check(body[0] ^ np.eye(1, len(body[0]), 5, dtype=np.uint8)[0])


def test_a_crc_with_no_catalogue_name_is_still_recovered() -> None:
    """CRC-16 with poly 0x8408 (a reflected variant nobody catalogues here), init and final XOR
    chosen arbitrarily: the generator and conventions are found, the name is None."""
    from dsp.synth.bits import Crc

    odd = Crc("odd", 16, 0x3D65, 0x1234, False, False, 0xBEEF, 0)
    rng = np.random.default_rng(6)
    rows = []
    for _ in range(80):
        body = rng.integers(0, 2, 96, dtype=np.uint8)
        rows.append(np.concatenate([body, odd.bits(body)]))
    fit = recover_crc(np.array(rows))
    assert fit is not None
    assert (fit.width, fit.poly, fit.refin, fit.refout) == (16, 0x3D65, False, False)
    assert fit.name is None and fit.passes == fit.heldout


def test_a_few_corrupted_frames_do_not_stop_the_crc_fit() -> None:
    spec = FrameSpec(payload_bytes=40)
    bits, _ = make(spec, 120, seed=7)
    noisy = flip(bits, 1e-4, seed=8)  # a few percent of frames carry an error
    found = analyse_stream(noisy)
    assert found is not None and found.crc is not None
    assert found.crc.name == "CRC-16/CCITT-FALSE"
    assert found.crc.passes >= 0.85 * found.crc.heldout


def test_frames_with_no_crc_give_no_fit() -> None:
    """The null case: random bodies. No generator divides their XORs."""
    rng = np.random.default_rng(10)
    rows = np.hstack(
        [np.tile(sync_bits("CCSDS ASM"), (100, 1)), rng.integers(0, 2, (100, 200), dtype=np.uint8)]
    )
    assert recover_crc(rows[:, 32:]) is None
    found = analyse_stream(rows.ravel())
    assert found is not None and found.crc is None


def test_crc_recovery_refuses_too_few_frames_and_odd_lengths() -> None:
    rng = np.random.default_rng(11)
    assert recover_crc(rng.integers(0, 2, (6, 100), dtype=np.uint8)) is None
    # A reflected-input CRC needs whole bytes of data: 13 data bits can't be one, and no other
    # variant fits random rows either.
    assert recover_crc(rng.integers(0, 2, (60, 13 + 16), dtype=np.uint8)) is None


# --- polynomial helpers used by the fit -----------------------------------------------------


def test_the_crc_generator_is_the_gcd_of_frame_xors() -> None:
    g = (1 << 16) | 0x1021
    a, b = 0xACE1DEAD1234, 0x0F0F13579BDF
    assert pmod(pgcd(pmul(a, g), pmul(b, g)), g) == 0  # g divides both multiples, so their gcd
    assert plcm(g, g) == g


def test_the_autocorrelation_screen_separates_framed_from_structureless_streams() -> None:
    from dsp.blind_framing import structure_z

    bits, _ = make(FrameSpec(), 140)
    assert structure_z(bits) > 8
    rng = np.random.default_rng(12)
    assert max(structure_z(rng.integers(0, 2, 80_000, dtype=np.uint8)) for _ in range(20)) < 5


@pytest.mark.slow
def test_no_sync_word_is_discovered_in_300_structureless_streams() -> None:
    """The null control for the blind search: random bits and shuffled real frames."""
    rng = np.random.default_rng(2026)
    found = 0
    for i in range(300):
        if i % 2:
            bits = rng.integers(0, 2, 80_000, dtype=np.uint8)
        else:
            bits = rng.permutation(make(FrameSpec(), 140, seed=i)[0])
        result = discover_sync(bits)
        found += result is not None and result.verified
    assert found == 0
