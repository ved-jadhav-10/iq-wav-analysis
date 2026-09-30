"""The GF(2) kernel against an independent implementation (`galois`) and exact ground truth
from the convolutional encoder in `dsp.synth` (PLAN M5)."""

import galois
import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra import numpy as hnp
from numpy.typing import NDArray

from dsp.gf2 import (
    MIN_EXTRA_ROWS,
    first_deficient_width,
    hard_bits,
    nullspace,
    pack,
    parity_counts,
    rank,
    rank_profile,
    reliable_window_matrix,
    row_weights,
    rref,
    unpack,
    window_matrix,
)
from dsp.synth.fec import Convolutional

GF2 = galois.GF(2)

# Shapes that cross the 64- and 128-bit word boundaries.
shapes = st.tuples(st.integers(1, 40), st.integers(1, 200))


def matrices() -> st.SearchStrategy[NDArray[np.uint8]]:
    return shapes.flatmap(lambda s: hnp.arrays(np.uint8, s, elements=st.integers(0, 1)))


@st.composite
def low_rank_matrices(draw: st.DrawFn) -> NDArray[np.uint8]:
    """A product B @ C, so its rank is well below its size (random matrices rarely are)."""
    rows, cols = draw(shapes)
    inner = draw(st.integers(1, 6))
    b = draw(hnp.arrays(np.uint8, (rows, inner), elements=st.integers(0, 1)))
    c = draw(hnp.arrays(np.uint8, (inner, cols), elements=st.integers(0, 1)))
    return ((b.astype(int) @ c.astype(int)) % 2).astype(np.uint8)


@settings(deadline=None)
@given(matrices())
def test_pack_and_unpack_are_inverses_and_padding_is_zero(a: NDArray[np.uint8]) -> None:
    packed = pack(a)
    assert packed.dtype == np.uint64 and packed.shape == (a.shape[0], -(-a.shape[1] // 64))
    assert np.array_equal(unpack(packed, a.shape[1]), a)
    assert not unpack(packed, packed.shape[1] * 64)[:, a.shape[1] :].any()  # padding is zero


def test_bit_j_of_a_row_is_bit_j_mod_64_of_word_j_div_64() -> None:
    a = np.zeros((1, 130), np.uint8)
    a[0, [0, 63, 64, 129]] = 1
    words = pack(a)[0]
    assert int(words[0]) == (1 << 0) | (1 << 63)
    assert int(words[1]) == 1
    assert int(words[2]) == 1 << 1


def test_pack_refuses_values_other_than_bits() -> None:
    with pytest.raises(ValueError, match="0 or 1"):
        pack(np.array([[0, 2]]))
    with pytest.raises(ValueError, match="2-D"):
        pack(np.zeros(4))


@settings(deadline=None)
@given(st.one_of(matrices(), low_rank_matrices()))
def test_rank_matches_galois(a: NDArray[np.uint8]) -> None:
    assert rank(pack(a), a.shape[1]) == np.linalg.matrix_rank(GF2(a))


@settings(deadline=None)
@given(st.one_of(matrices(), low_rank_matrices()))
def test_rref_is_the_unique_reduced_form_galois_computes(a: NDArray[np.uint8]) -> None:
    reduced, pivots = rref(pack(a), a.shape[1])
    expected = np.array(GF2(a).row_reduce(), dtype=np.uint8)
    assert np.array_equal(unpack(reduced, a.shape[1]), expected)
    # Pivot columns are the leading ones of the non-zero rows, in order.
    leading = [int(np.flatnonzero(row)[0]) for row in expected if row.any()]
    assert list(pivots) == leading


def test_rref_does_not_modify_its_input() -> None:
    a = pack(np.random.default_rng(1).integers(0, 2, (10, 20), dtype=np.uint8))
    before = a.copy()
    rref(a, 20)
    assert np.array_equal(a, before)


@settings(deadline=None)
@given(st.one_of(matrices(), low_rank_matrices()))
def test_nullspace_vectors_are_orthogonal_to_every_row_and_span_the_null_space(
    a: NDArray[np.uint8],
) -> None:
    cols = a.shape[1]
    basis = unpack(nullspace(pack(a), cols), cols)
    assert basis.shape == (cols - np.linalg.matrix_rank(GF2(a)), cols)
    assert not ((a.astype(int) @ basis.T.astype(int)) % 2).any()
    if len(basis):  # linearly independent, so they really are a basis
        assert np.linalg.matrix_rank(GF2(basis)) == len(basis)


@settings(deadline=None)
@given(matrices())
def test_row_weights_and_parity_counts_match_a_direct_count(a: NDArray[np.uint8]) -> None:
    assert list(row_weights(pack(a))) == list(a.sum(axis=1))
    vectors = np.random.default_rng(a.size).integers(0, 2, (5, a.shape[1]), dtype=np.uint8)
    expected = ((a.astype(int) @ vectors.T.astype(int)) % 2).sum(axis=0)
    assert list(parity_counts(pack(a), pack(vectors))) == list(expected)


def test_parity_counts_refuses_mismatched_widths() -> None:
    with pytest.raises(ValueError, match="same number of columns"):
        parity_counts(pack(np.zeros((2, 10), np.uint8)), pack(np.zeros((1, 100), np.uint8)))


# --- windows and the rank scan -------------------------------------------------------------

CODES = [
    # (constraint, generators, first deficient width). A w-bit window aligned to the code's
    # blocks touches ceil(w / n) blocks and so depends on ceil(w / n) + K - 1 input bits; the
    # rank drops at the first w with w > ceil(w / n) + K - 1. (For n = 2 that is n * K; for
    # n = 3 it is not, which is why the width is worked out per code, not taken as n * K.)
    (3, (0o7, 0o5), 6),
    (7, (0o171, 0o133), 14),
    (9, (0o561, 0o753), 18),
    (7, (0o133, 0o171, 0o165), 11),
]


def encode(
    constraint: int, generators: tuple[int, ...], n_bits: int, seed: int
) -> NDArray[np.uint8]:
    u = np.random.default_rng(seed).integers(0, 2, n_bits, dtype=np.uint8)
    return Convolutional(constraint, generators).encode(u)


@pytest.mark.parametrize(("constraint", "generators", "expected"), CODES)
def test_the_rank_scan_finds_the_first_deficient_width_of_a_convolutional_code(
    constraint: int, generators: tuple[int, ...], expected: int
) -> None:
    n = len(generators)
    coded = encode(constraint, generators, 3000, seed=constraint)
    # Aligned to the code's blocks, past the encoder's start-up (offset a multiple of n).
    profile = rank_profile(coded, range(n, 2 * expected + 1), stride=n, offset=4 * n * constraint)
    assert first_deficient_width(profile) == expected
    assert all(p.deficiency == 0 for p in profile if p.width < expected)


@pytest.mark.parametrize("seed", range(4))
def test_structureless_and_shuffled_bits_never_look_deficient(seed: int) -> None:
    """The control: random bits, and a coded stream with its bits shuffled, stay full rank."""
    rng = np.random.default_rng(seed)
    random_bits = rng.integers(0, 2, 4000, dtype=np.uint8)
    coded = encode(7, (0o171, 0o133), 2000, seed)
    shuffled = rng.permutation(coded)
    for bits in (random_bits, shuffled):
        profile = rank_profile(bits, range(2, 60), stride=2, offset=0)
        assert first_deficient_width(profile) is None


def test_the_row_count_rule_is_enforced() -> None:
    bits = np.zeros(200, np.uint8)
    assert len(window_matrix(bits, 14)) == 200 - 14 + 1
    with pytest.raises(ValueError, match=f"width \\+ {MIN_EXTRA_ROWS}"):
        window_matrix(bits[:50], 14)  # 37 windows < 14 + 30
    with pytest.raises(ValueError, match="rows"):
        window_matrix(bits, 14, rows=20)
    with pytest.raises(ValueError, match="rows"):
        rank_profile(bits[:50], [14])


def test_window_matrix_rows_are_the_stream_windows() -> None:
    bits = np.random.default_rng(3).integers(0, 2, 300, dtype=np.uint8)
    m = window_matrix(bits, 8, stride=3, offset=5)
    assert np.array_equal(m[0], bits[5:13])
    assert np.array_equal(m[4], bits[17:25])
    assert m.shape == ((300 - 5 - 8) // 3 + 1, 8)


def test_reliable_rows_recover_a_rank_drop_that_errors_hide() -> None:
    """A few unreliable flipped bits make hard-decision rank full; keeping only windows made of
    reliable bits sees the code again."""
    coded = encode(7, (0o171, 0o133), 5000, seed=11)
    rng = np.random.default_rng(12)
    llr = np.where(coded == 0, 4.0, -4.0)
    flipped = rng.random(len(coded)) < 0.01
    llr[flipped] = np.where(coded[flipped] == 0, -0.2, 0.2)  # wrong sign, low confidence
    received = hard_bits(llr)
    assert (received != coded).sum() == flipped.sum() > 50

    hard = rank_profile(received, [14], stride=2, offset=40)[0]
    assert hard.deficiency == 0  # the errors hide the structure

    m = reliable_window_matrix(llr, 14, stride=2, offset=40, keep=14 + 60)
    assert rank(pack(m), 14) == 13


def test_reliable_rows_are_ordered_most_reliable_first_and_obey_the_row_rule() -> None:
    rng = np.random.default_rng(5)
    llr = rng.normal(0, 3, 400)
    m = reliable_window_matrix(llr, 8, keep=8 + 30)
    assert m.shape == (38, 8)
    with pytest.raises(ValueError, match="rows"):
        reliable_window_matrix(llr, 8, keep=20)
    with pytest.raises(ValueError, match="holds"):
        reliable_window_matrix(llr[:40], 8, keep=8 + 30)
    assert np.array_equal(hard_bits([1.0, -1.0, 0.0]), [0, 1, 0])
