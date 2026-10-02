"""The Reed-Solomon decoder (`dsp.fec.rs`, Numba) against `galois`, the library whose algorithm it
follows: the same corrected words and error counts on code words with 0 .. 255 symbol errors and
on pure noise, for the CCSDS RS(255, 223) and DVB's shortened RS(204, 188), and `detect` against
the zero-syndrome test."""

from typing import Any

import galois  # pyright: ignore[reportMissingTypeStubs]
import numpy as np

from dsp.fec import rs
from dsp.synth.fec import RS_CCSDS, RS_DVB


def _oracle(field_poly: int, first_root: int, root_power: int, k_full: int) -> Any:
    field = galois.GF(2**8, irreducible_poly=field_poly)
    alpha = field.primitive_element**root_power
    return galois.ReedSolomon(255, k_full, c=first_root, field=field, alpha=alpha, systematic=True)


def _full_words(
    encoder: Any, rng: np.random.Generator, count: int, errors: list[int]
) -> np.ndarray:
    """`count` full-length (255-byte) code words of `encoder`, each with the next entry of
    `errors` (cycled) random symbols replaced by random different values."""
    n, k = encoder.n, encoder.k
    messages = rng.integers(0, 256, (count, k), dtype=np.uint8)
    words = np.frombuffer(encoder.encode(messages.tobytes()), np.uint8).reshape(count, n).copy()
    padded = np.hstack([np.zeros((count, 255 - n), np.uint8), words])
    for i in range(count):
        flips = errors[i % len(errors)]
        where = rng.choice(n, flips, replace=False) + (255 - n)
        padded[i, where] ^= rng.integers(1, 256, flips, dtype=np.uint8)
    return padded


def test_the_decoder_matches_galois_word_for_word() -> None:
    params = (rs.CCSDS_FIELD_POLY, rs.CCSDS_FIRST_ROOT, rs.CCSDS_ROOT_POWER, 223)
    oracle = _oracle(*params)
    rng = np.random.default_rng(26147)
    errors = [0, 1, 2, 3, 5, 8, 12, 15, 16, 17, 18, 20, 24, 40, 100, 255]
    words = _full_words(RS_CCSDS, rng, 16 * 24, errors)
    every = np.vstack([words, rng.integers(0, 256, (300, 255), dtype=np.uint8)])  # and noise
    expected_words, expected_errors = oracle.decode(
        oracle.field(every), output="codeword", errors=True
    )
    fixed, counts = rs.correct(every)
    assert np.array_equal(counts, np.asarray(expected_errors))
    assert np.array_equal(fixed, np.asarray(expected_words, np.uint8))
    assert np.array_equal(rs.detect(every), np.asarray(oracle.detect(oracle.field(every))))
    assert (counts >= 0).sum() > 100 and (counts < 0).sum() > 100  # both outcomes are exercised


def test_the_shortened_dvb_code_corrects_up_to_t_and_gives_up_beyond_it() -> None:
    """The other field polynomial and a first root of 0, against the synth's own encoder."""
    rng = np.random.default_rng(8)
    kwargs: dict[str, Any] = {"n": 204, "k": 188, "field_poly": 0x11D, "first_root": 0}
    for flips in (0, 1, 4, 8, 9, 12):
        message = rng.integers(0, 256, 188, dtype=np.uint8).tobytes()
        word = bytearray(RS_DVB.encode(message))
        for i in rng.choice(204, flips, replace=False):
            word[i] ^= int(rng.integers(1, 256))
        got = rs.decode_block(bytes(word), root_power=1, **kwargs)
        assert got == ((message, flips) if flips <= 8 else None)


def test_decode_block_returns_the_message_the_synth_encoded() -> None:
    rng = np.random.default_rng(5)
    message = rng.integers(0, 256, 223, dtype=np.uint8).tobytes()
    word = bytearray(RS_CCSDS.encode(message))
    for i in (0, 100, 254):
        word[i] ^= 0x41
    assert rs.decode_block(bytes(word)) == (message, 3)


def test_decode_stream_finds_the_grid_and_corrects_every_word() -> None:
    rng = np.random.default_rng(6)
    messages = rng.integers(0, 256, (6, 223), dtype=np.uint8)
    stream = bytearray(RS_CCSDS.encode(messages.tobytes()))
    stream[300] ^= 0xFF  # one symbol error in the second word
    bits = np.unpackbits(np.frombuffer(bytes(stream), np.uint8))
    lead = rng.integers(0, 2, 8 * 17 + 3, dtype=np.uint8)  # a start in the middle of a byte
    found = rs.decode_stream(np.concatenate([lead, bits]))
    assert found is not None
    assert found.alignment == 3
    assert found.corrected == 1 and found.failed == 0
    assert found.codewords >= 5
    got = np.packbits(found.bits).reshape(found.codewords, 223)
    assert np.array_equal(got, messages[-found.codewords :])


def test_decode_stream_returns_none_on_noise() -> None:
    noise = np.random.default_rng(7).integers(0, 2, 8 * 255 * 6, dtype=np.uint8)
    assert rs.decode_stream(noise) is None
