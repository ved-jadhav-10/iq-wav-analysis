"""The blind block-interleaver finder against exact ground truth from dsp.synth (PLAN M5)."""

from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from dsp.blind_interleaver import find_blocks, scan_strides
from dsp.synth import fec
from dsp.synth import interleave as il

CODE = fec.Convolutional(7, fec.K7)


def coded(seed: int, n_bits: int = 100_000) -> NDArray[np.uint8]:
    rng = np.random.default_rng(seed)
    return CODE.encode(rng.integers(0, 2, n_bits).astype(np.uint8))


def interleaved(rows: int, cols: int, *, seed: int = 1, ber: float = 0.0, lead: int = 11) -> Any:
    spec = il.Block(rows, cols)
    stream = coded(seed)
    blocks = stream[: len(stream) // spec.size * spec.size]
    out = il.interleave(blocks, spec).astype(np.uint8)
    flips = np.random.default_rng(seed + 100).random(len(out)) < ber
    return (out ^ flips)[lead:]


@pytest.mark.parametrize(
    ("rows", "cols", "ber"),
    [(10, 30, 0.0), (20, 40, 0.02), (37, 19, 0.0), (12, 25, 0.02), (32, 64, 0.02), (64, 100, 0.02)],
    ids=str,
)
def test_the_block_shape_is_among_the_candidates(rows: int, cols: int, ber: float) -> None:
    found = find_blocks(interleaved(rows, cols, ber=ber))
    assert (rows, cols) in [(b.block.rows, b.block.cols) for b in found]
    assert len(found) <= 6
    stride = next(b.stride for b in found if b.block.rows == rows)
    assert stride.stride == rows and stride.z >= 7


def test_the_short_half_of_a_tie_is_offered_with_its_double() -> None:
    """Joins two bits apart fold as sharply at half the row length: both are candidates."""
    lengths = sorted({b.block.cols for b in find_blocks(interleaved(10, 30))})
    assert lengths == [15, 30]


def test_the_evidence_names_the_stride_the_syndrome_and_the_row_length() -> None:
    (first, *_) = find_blocks(interleaved(20, 40))
    assert "Every 20th received bit" in first.evidence
    assert "sigma below chance" in first.evidence and "every 40 bits" in first.evidence


def rng_bits(seed: int, n: int) -> NDArray[np.uint8]:
    return np.random.default_rng(seed).integers(0, 2, n).astype(np.uint8)


NULLS = {
    "random": lambda: rng_bits(1, 200_000),
    "zeros": lambda: np.zeros(200_000, np.uint8),
    "alternating": lambda: np.tile(np.array([0, 1], np.uint8), 100_000),
    "repeated": lambda: np.tile(rng_bits(2, 100), 2_000),
    "coded, not interleaved": lambda: coded(3)[:200_000],
    "interleaved, then shuffled": lambda: np.random.default_rng(4).permutation(interleaved(20, 40)),
}


@pytest.mark.parametrize("name", NULLS)
def test_nothing_is_found_where_there_is_no_block_interleaver(name: str) -> None:
    assert find_blocks(NULLS[name]()) == ()


def test_random_streams_show_no_stride_in_many_trials() -> None:
    hits = sum(bool(scan_strides(rng_bits(s, 60_000))) for s in range(200))
    assert hits == 0


def test_a_stream_with_structure_at_many_strides_is_refused_not_read() -> None:
    """A period-3 pattern satisfies the parity checks at every multiple of 3: too many strides
    to be an interleaver, so none is claimed."""
    assert scan_strides(np.tile(np.array([1, 0, 0], np.uint8), 80_000)) == ()
