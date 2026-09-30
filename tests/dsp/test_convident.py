"""Blind convolutional-code identification against exact ground truth from `dsp.synth` (PLAN M5).

The truth for each stream is the encoder that made it, so a pass means the search recovered the
generators, constraint length, branch count, block offset and polarity, not just something that
decodes."""

import math

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from dsp.fec.convident import identify_convolutional, to_octal
from dsp.fec.viterbi import ConvCode, decode
from dsp.gf2.poly import pdivmod, pgcd, plcm, pmul
from dsp.synth.fec import Convolutional

CODES = {
    "K3 r1/2 (7,5)": (3, (0o7, 0o5)),
    "K7 r1/2 (171,133)": (7, (0o171, 0o133)),
    "K9 r1/2 (561,753)": (9, (0o561, 0o753)),
    "K7 r1/3 (133,171,165)": (7, (0o133, 0o171, 0o165)),
    "K5 r1/4 (25,33,37,35)": (5, (0o25, 0o33, 0o37, 0o35)),
}


def make(
    constraint: int, generators: tuple[int, ...], n_bits: int, seed: int
) -> tuple[NDArray[np.uint8], NDArray[np.uint8]]:
    u = np.random.default_rng(seed).integers(0, 2, n_bits, dtype=np.uint8)
    return u, Convolutional(constraint, generators).encode(u)


def clean_llr(bits: NDArray[np.uint8]) -> NDArray[np.float64]:
    return np.where(bits == 0, 4.0, -4.0)


# --- polynomial arithmetic ---------------------------------------------------------------

polys = st.integers(1, 1 << 24)


@given(polys, polys)
def test_polynomial_gcd_and_lcm_are_a_gcd_and_lcm(a: int, b: int) -> None:
    g = pgcd(a, b)
    assert pdivmod(a, g)[1] == 0 and pdivmod(b, g)[1] == 0
    lcm = plcm(a, b)
    assert pdivmod(lcm, a)[1] == 0 and pdivmod(lcm, b)[1] == 0
    assert pmul(g, lcm) == pmul(a, b)  # gcd * lcm = a * b, as for integers


@given(polys, polys)
def test_polynomial_division_reconstructs(a: int, b: int) -> None:
    q, r = pdivmod(a, b)
    assert pmul(q, b) ^ r == a
    assert r == 0 or r.bit_length() < b.bit_length()


def test_octal_generators_put_the_newest_tap_in_the_top_bit() -> None:
    # 0o171 = 1111001: taps at delays 0, 1, 2, 3 and 6 (MSB first).
    poly = sum(1 << i for i in (0, 1, 2, 3, 6))
    assert to_octal(poly, 7) == 0o171
    assert to_octal(1 << 6, 7) == 0o1


# --- identification ------------------------------------------------------------------------


@pytest.mark.parametrize("name", CODES)
@pytest.mark.parametrize("drop", [0, 1, 5])
def test_a_clean_stream_gives_back_the_exact_code_at_the_right_offset(name: str, drop: int) -> None:
    constraint, generators = CODES[name]
    n = len(generators)
    _, coded = make(constraint, generators, 6000, seed=constraint + drop)
    search = identify_convolutional(clean_llr(coded[drop:]))
    found = search.found
    assert found is not None, [a.reason for a in search.ledger if a.n == n]
    assert (found.n, found.code.constraint, found.code.generators) == (n, constraint, generators)
    assert found.offset == (-drop) % n  # the first whole block starts here
    assert found.p_value < found.threshold


def test_an_inverted_stream_is_reported_inverted_when_the_check_can_tell() -> None:
    """(7,5) has checks of odd weight, so a complemented stream fails them; the search finds the
    code only on the complement, and says so."""
    _, coded = make(3, (0o7, 0o5), 6000, seed=1)
    upright = identify_convolutional(clean_llr(coded)).found
    inverted = identify_convolutional(clean_llr(1 - coded)).found
    assert upright is not None and inverted is not None
    assert (upright.inverted, inverted.inverted) == (False, True)
    assert inverted.code.generators == (0o7, 0o5)


@pytest.mark.parametrize(
    "name", ["K7 r1/2 (171,133)", "K9 r1/2 (561,753)", "K7 r1/3 (133,171,165)"]
)
def test_a_noisy_soft_stream_is_identified_and_then_decodes_with_the_identified_code(
    name: str,
) -> None:
    """BPSK at 2.5 dB Es/N0 (about 3 % raw bit errors): the code is found from the reliable
    windows, and the general Viterbi decoder recovers the message with it."""
    constraint, generators = CODES[name]
    n = len(generators)
    drop = 3
    u, coded = make(constraint, generators, 12_000, seed=20)
    rng = np.random.default_rng(21)
    sigma = math.sqrt(1 / (2 * 10 ** (2.5 / 10)))
    rx = (1 - 2.0 * coded) + rng.normal(0, sigma, len(coded))
    llr = 2 * rx / sigma**2
    assert 0.015 < ((rx < 0) != (coded == 1)).mean() < 0.06

    found = identify_convolutional(llr[drop:]).found
    assert found is not None
    assert (found.code.constraint, found.code.generators) == (constraint, generators)

    aligned = llr[drop + found.offset :]
    bits = decode(aligned[: (len(aligned) // n) * n], found.code)
    first = -(-drop // n)  # message bit of the first whole block
    truth = u[first : first + len(bits)]
    errors = (bits[: len(truth)] != truth)[constraint * 4 :].mean()  # past the start-up
    assert errors < 0.01


@pytest.mark.parametrize("seed", range(8))
def test_structureless_streams_are_never_identified(seed: int) -> None:
    """Null controls: random bits, and a real coded stream with its bits shuffled."""
    rng = np.random.default_rng(seed)
    _, coded = make(7, (0o171, 0o133), 5000, seed=seed)
    for bits in (rng.integers(0, 2, 12_000, dtype=np.uint8), rng.permutation(coded)):
        search = identify_convolutional(clean_llr(bits))
        assert search.found is None
        assert not any(a.accepted for a in search.ledger)


def test_the_search_counts_every_hypothesis_and_corrects_for_them() -> None:
    search = identify_convolutional(clean_llr(make(7, (0o171, 0o133), 3000, 4)[1]), max_n=3)
    # Both polarities x (n=2: 2 offsets, n=3: 3 offsets) x 9 widths (2..10 blocks minus one).
    assert search.tried == 2 * (2 + 3) * 9
    assert len(search.ledger) == 2 + 3  # polarity is read from the checks, not searched twice
    assert all(a.threshold == search.alpha / search.tried for a in search.ledger)
    assert all(a.reason for a in search.ledger)


def test_a_stream_too_short_to_search_is_reported_not_guessed() -> None:
    search = identify_convolutional(clean_llr(make(7, (0o171, 0o133), 30, 5)[1]), max_n=2)
    assert search.found is None
    assert all("too short" in a.reason for a in search.ledger)


def test_a_wrong_constraint_bound_is_reported_not_returned() -> None:
    _, coded = make(9, (0o561, 0o753), 6000, seed=6)
    search = identify_convolutional(clean_llr(coded), max_n=2, max_constraint=7)
    assert search.found is None


def test_identified_code_is_a_convcode_the_viterbi_decoder_accepts() -> None:
    _, coded = make(3, (0o7, 0o5), 2000, seed=7)
    found = identify_convolutional(clean_llr(coded), max_n=2).found
    assert found is not None
    assert isinstance(found.code, ConvCode) and found.code.n == 2


@pytest.mark.slow
def test_no_false_identification_on_1000_null_streams() -> None:
    """PLAN §2: 0 accepted decodes on >= 1,000 null files, for this search on its own: random
    hard bits, Gaussian soft values, and coded streams with their bits shuffled."""
    rng = np.random.default_rng(2026)
    accepted = 0
    for i in range(1000):
        if i % 3 == 0:
            llr = clean_llr(rng.integers(0, 2, 12_000, dtype=np.uint8))
        elif i % 3 == 1:
            llr = rng.normal(0, 3, 12_000)
        else:
            _, coded = make(7, (0o171, 0o133), 6000, seed=i)
            llr = clean_llr(rng.permutation(coded))
        accepted += identify_convolutional(llr).found is not None
    assert accepted == 0
