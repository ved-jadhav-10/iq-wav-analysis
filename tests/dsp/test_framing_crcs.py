"""The CRC catalogue of `dsp.framing`: every entry against its published check value, the
vectorised check against the bit-by-bit one, and frames carrying each width found and named."""

import numpy as np
import pytest

from dsp.framing import CRCS, SYNC_WORDS, Crc, find_frames

CHECK_INPUT = np.unpackbits(np.frombuffer(b"123456789", np.uint8))


def frames_with(crc: Crc, count: int = 12, payload_bytes: int = 24, seed: int = 0) -> np.ndarray:
    """A stream of sync word | payload | CRC frames, ready to be searched."""
    rng = np.random.default_rng(seed)
    word = SYNC_WORDS[0].bits()
    out = []
    for _ in range(count):
        payload = rng.integers(0, 2, payload_bytes * 8, dtype=np.uint8)
        field = np.array(
            [(crc.compute(payload) >> (crc.width - 1 - i)) & 1 for i in range(crc.width)]
        )
        out.append(np.concatenate([word, payload, field.astype(np.uint8)]))
    return np.concatenate(out)


def test_the_catalogue_has_distinct_names_and_a_check_value_for_every_entry() -> None:
    assert len({c.name for c in CRCS}) == len(CRCS)
    assert all(c.check != 0 for c in CRCS)
    assert {c.width for c in CRCS} == {8, 16, 32}


@pytest.mark.parametrize("crc", CRCS, ids=lambda c: c.name)
def test_every_entry_reproduces_the_catalogues_check_value(crc: Crc) -> None:
    assert crc.compute(CHECK_INPUT) == crc.check


@pytest.mark.parametrize("crc", CRCS, ids=lambda c: c.name)
def test_the_vectorised_check_equals_the_bit_by_bit_one_at_any_length(crc: Crc) -> None:
    rng = np.random.default_rng(crc.width + crc.poly)
    for length in (8, 43, 200):  # includes lengths that are not whole bytes
        rows = rng.integers(0, 2, (5, length), dtype=np.uint8)
        assert crc.compute_many(rows).tolist() == [crc.compute(r) for r in rows]


@pytest.mark.parametrize(
    "name", ["CRC-8/MAXIM", "CRC-16/KERMIT", "CRC-16/MODBUS", "CRC-32", "CRC-32C"]
)
def test_frames_carrying_a_crc_of_each_width_pass_it_and_are_named(name: str) -> None:
    crc = next(c for c in CRCS if c.name == name)
    found = find_frames(frames_with(crc), SYNC_WORDS[0])
    assert found is not None and found.crc is not None
    assert found.crc.name == name
    assert found.passes == found.complete == 12
    assert all(f.crc == "pass" for f in found.frames)


def test_corrupted_frames_fail_and_the_rest_still_pass() -> None:
    crc = next(c for c in CRCS if c.name == "CRC-16/CCITT-FALSE")
    stream = frames_with(crc, count=10)
    frame_length = 32 + 24 * 8 + 16
    for k in (2, 7):  # flip one payload bit in two frames
        stream[k * frame_length + 40] ^= 1
    found = find_frames(stream, SYNC_WORDS[0])
    assert found is not None and found.crc is not None
    assert [f.crc for f in found.frames].count("fail") == 2
    assert found.passes == 8 and found.complete == 10
