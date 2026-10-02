"""The standard LDPC catalogue, encoder and min-sum decoder against exact ground truth: the
parity-check matrices' structure (and a checksum of their edge lists published by labrador-ldpc,
MIT), encoding through two independent paths (`dsp.gf2` and `galois`), decoding of BPSK over
AWGN to the exact message, and the alignment screen on a stream at a known offset."""

import numpy as np
import pytest
from numpy.typing import NDArray

from dsp.fec import ldpc, ldpc_data
from dsp.fec.ldpc import LdpcCode
from dsp.synth.fec import StandardLdpc, standard_ldpc

# name -> (n, k, punctured, edges)
EXPECTED = {
    "IEEE 802.11n n=648 r1/2": (648, 324, 0, 88 * 27),
    "IEEE 802.11n n=648 r2/3": (648, 432, 0, 88 * 27),
    "IEEE 802.11n n=648 r3/4": (648, 486, 0, 88 * 27),
    "IEEE 802.11n n=648 r5/6": (648, 540, 0, 88 * 27),
    "CCSDS TC n=128 k=64": (128, 64, 0, 512),
    "CCSDS TC n=256 k=128": (256, 128, 0, 1024),
    "CCSDS TC n=512 k=256": (512, 256, 0, 2048),
    "CCSDS TM k=1024 r1/2": (2560, 1024, 512, 7680),
    "CCSDS TM k=1024 r2/3": (1792, 1024, 256, 5888),
    "CCSDS TM k=1024 r4/5": (1408, 1024, 128, 4992),
    "CCSDS TM k=4096 r1/2": (10240, 4096, 2048, 30720),
    "CCSDS TM k=4096 r2/3": (7168, 4096, 1024, 23552),
    "CCSDS TM k=4096 r4/5": (5632, 4096, 512, 19968),
}

# labrador-ldpc's own test (MIT, Copyright 2017 Adam Greig): CRC-32 over the (check, variable)
# pairs of each code in the order its tables give them, "manually verified" there.
LABRADOR_EDGE_CRC = {
    "CCSDS TC n=128 k=64": 0x13A9D28D,
    "CCSDS TC n=256 k=128": 0xC3CC7625,
    "CCSDS TC n=512 k=256": 0x66EA9A48,
    "CCSDS TM k=1024 r4/5": 0xB643C99E,
    "CCSDS TM k=1024 r2/3": 0x8169E0CF,
    "CCSDS TM k=1024 r1/2": 0x599A0807,
    "CCSDS TM k=4096 r4/5": 0xD0E794B1,
    "CCSDS TM k=4096 r2/3": 0xBD0AB764,
    "CCSDS TM k=4096 r1/2": 0x9003014C,
}


def _crc32_u16(crc: int, data: int) -> int:
    crc ^= data
    for _ in range(16):
        crc = (crc >> 1) ^ (0xEDB88320 if crc & 1 else 0)
    return crc


def _edge_crc(name: str) -> int:
    """Rebuild the edge list straight from `ldpc_data` in table order and checksum it."""
    if name.startswith("CCSDS TC"):
        n = int(name.split("n=")[1].split()[0])
        blocks, m, tm = ldpc_data.CCSDS_TC[n], n // 8, False
    else:
        k = int(name.split("k=")[1].split()[0])
        rate = name.split(" r")[-1]
        blocks, m, tm = ldpc_data.CCSDS_TM[rate], k // {"1/2": 2, "2/3": 4, "4/5": 8}[rate], True
    crc = 0xFFFFFFFF
    for r, line in enumerate(blocks):
        for c, terms in enumerate(line):
            for term in terms:
                perm = ldpc._tm_permutation(term, m) if tm and term else None  # pyright: ignore[reportPrivateUsage]
                for check in range(m):
                    if perm is not None:
                        col = int(perm[check])
                    else:
                        col = (check + (0 if tm else term)) % m
                    crc = _crc32_u16(_crc32_u16(crc, r * m + check), c * m + col)
    return crc


def _code(name: str) -> LdpcCode:
    return ldpc.by_name(name)


def _llr(
    word: NDArray[np.uint8], ebn0_db: float, rate: float, rng: np.random.Generator
) -> NDArray[np.float64]:
    """BPSK (bit 0 -> +1) over AWGN as LLRs, positive = bit 0, at the given Eb/N0."""
    sigma = np.sqrt(1 / (2 * rate * 10 ** (ebn0_db / 10)))
    y = 1.0 - 2.0 * word + sigma * rng.standard_normal(word.shape)
    return 2 * y / sigma**2


def _messages(code: LdpcCode, rows: int, seed: int) -> NDArray[np.uint8]:
    return np.random.default_rng(seed).integers(0, 2, (rows, code.k), dtype=np.uint8)


# -- the catalogue -------------------------------------------------------------------------------


def test_the_catalogue_holds_every_expected_code_once() -> None:
    assert [c.name for c in ldpc.CATALOGUE] == list(EXPECTED)
    for code in ldpc.CATALOGUE:
        assert code.source


@pytest.mark.parametrize("name", list(EXPECTED))
def test_dimensions_and_rank_match_the_standard(name: str) -> None:
    n, k, punctured, edges = EXPECTED[name]
    code = _code(name)
    assert (code.n, code.k, code.punctured, len(code.cols)) == (n, k, punctured, edges)
    assert code.transmitted == n - punctured
    assert code.checks == n - k
    # Full rank: the code's dimension is exactly n - rank(H) = k.
    assert n - code.rank == k
    assert int(code.row_weights.sum()) == int(code.column_weights.sum()) == edges
    assert code.column_weights.min() >= 1 and code.row_weights.min() >= 2


def test_weight_distributions_of_the_regular_looking_codes() -> None:
    # TC: every check has 8 edges; variable weights 3 and 5 (four block columns each).
    tc = _code("CCSDS TC n=256 k=128")
    assert set(tc.row_weights.tolist()) == {8}
    assert np.bincount(tc.column_weights).nonzero()[0].tolist() == [3, 5]
    assert int((tc.column_weights == 3).sum()) == 128 == int((tc.column_weights == 5).sum())
    # 802.11n: rates 2/3 and 5/6 are check-regular (11 and 22), r1/2 has weights 7 and 8, and
    # the first parity block column has weight 3 blocks, i.e. 12 per column at r1/2.
    assert set(_code("IEEE 802.11n n=648 r2/3").row_weights.tolist()) == {11}
    assert set(_code("IEEE 802.11n n=648 r5/6").row_weights.tolist()) == {22}
    assert set(_code("IEEE 802.11n n=648 r1/2").row_weights.tolist()) == {7, 8}
    # AR4JA r1/2: check degrees 3 and 6; variable degrees 1 (the degree-1 node), 2, 3 and 6
    # (the punctured node, 2 + 3 + 1 per block column).
    tm = _code("CCSDS TM k=1024 r1/2")
    assert np.bincount(tm.row_weights).nonzero()[0].tolist() == [3, 6]
    assert np.bincount(tm.column_weights).nonzero()[0].tolist() == [1, 2, 3, 6]
    assert set(tm.column_weights[tm.transmitted :].tolist()) == {6}


@pytest.mark.parametrize("name", list(LABRADOR_EDGE_CRC))
def test_ccsds_edge_lists_match_labradors_published_checksums(name: str) -> None:
    assert _edge_crc(name) == LABRADOR_EDGE_CRC[name]
    # ...and the catalogue's own (sorted) edge list is the same set of edges.
    code = _code(name)
    assert len(set(zip(code.rows.tolist(), code.cols.tolist(), strict=True))) == len(code.cols)


def test_ieee_80211n_first_rows_are_the_standards() -> None:
    # IEEE 802.11-2020 Annex F, n = 648 rate 1/2, first block row (a few columns of it).
    first = ldpc_data.IEEE_802_11N_648["1/2"][0]
    assert first[:5] == (0, -1, -1, -1, 0)
    assert first[12:14] == (1, 0)
    for rate, rows in (("1/2", 12), ("2/3", 8), ("3/4", 6), ("5/6", 4)):
        base = ldpc_data.IEEE_802_11N_648[rate]
        assert len(base) == rows and all(len(r) == 24 for r in base)
        # the dual-diagonal parity part: block column 24 - rows has weight 3 (a shift 1 first)
        assert base[0][24 - rows] == 1


def test_by_name_rejects_an_unknown_code() -> None:
    with pytest.raises(KeyError):
        ldpc.by_name("no such code")


# -- encoding ------------------------------------------------------------------------------------

ENCODE_NAMES = [n for n in EXPECTED if "k=4096" not in n]  # 4096: minutes of GF(2) elimination


@pytest.mark.parametrize("name", ENCODE_NAMES)
def test_encoded_words_satisfy_every_check_and_keep_the_message(name: str) -> None:
    code = _code(name)
    u = _messages(code, 3, seed=11)
    full = ldpc.encode(code, u, full=True)
    assert full.shape == (3, code.n)
    assert np.array_equal(full[:, : code.k], u)
    for word in full:
        assert not ldpc.syndrome(word, code).any()
    assert ldpc.syndrome_rate(full, code) == 0.0
    tx = ldpc.encode(code, u)
    assert np.array_equal(tx, full[:, : code.transmitted])
    assert ldpc.encode(code, u[0]).shape == (code.transmitted,)  # 1-D in, 1-D out


def test_encode_rejects_a_message_of_the_wrong_length() -> None:
    with pytest.raises(ValueError):
        ldpc.encode(_code("CCSDS TC n=128 k=64"), np.zeros(63, np.uint8))


@pytest.mark.parametrize(
    "name",
    ["IEEE 802.11n n=648 r5/6", "CCSDS TC n=128 k=64", "CCSDS TM k=1024 r4/5"],
)
def test_the_synth_encoder_agrees_with_the_decoder_side_encoder(name: str) -> None:
    code = _code(name)
    synth = standard_ldpc(code)
    assert isinstance(synth, StandardLdpc)
    assert (synth.k, synth.n) == (code.k, code.transmitted)
    u = _messages(code, 4, seed=5)
    # galois (synth) vs dsp.gf2 (ldpc): two eliminations that must give the same code word.
    assert np.array_equal(synth.encode(u.ravel()), ldpc.encode(code, u).ravel())
    truth = synth.truth()
    assert truth["name"] == name and truth["punctured"] == code.punctured
    assert truth["standard"] == code.family
    with pytest.raises(ValueError):
        synth.encode(np.zeros(code.k + 1, np.uint8))


# -- decoding ------------------------------------------------------------------------------------

DECODE_CASES = [  # name, Eb/N0 dB (about 1.5 dB above where the code starts to fail), words
    ("IEEE 802.11n n=648 r1/2", 3.5, 20),
    ("IEEE 802.11n n=648 r2/3", 4.0, 20),
    ("IEEE 802.11n n=648 r3/4", 4.5, 20),
    ("IEEE 802.11n n=648 r5/6", 5.0, 20),
    ("CCSDS TC n=128 k=64", 5.0, 20),
    ("CCSDS TC n=256 k=128", 4.5, 20),
    ("CCSDS TC n=512 k=256", 4.0, 20),
    ("CCSDS TM k=1024 r1/2", 3.5, 8),
    ("CCSDS TM k=1024 r2/3", 4.0, 8),
    ("CCSDS TM k=1024 r4/5", 4.5, 8),
]


@pytest.mark.parametrize(("name", "ebn0", "words"), DECODE_CASES)
def test_bpsk_over_awgn_decodes_to_the_exact_message(name: str, ebn0: float, words: int) -> None:
    code = _code(name)
    u = _messages(code, words, seed=21)
    tx = ldpc.encode(code, u)
    llr = _llr(tx, ebn0, code.k / code.transmitted, np.random.default_rng(22))
    hard, converged, iterations, unsat = ldpc.decode_many(llr, code, max_iter=50)
    assert converged.all() and not unsat.any()
    assert np.array_equal(hard[:, : code.k], u)
    assert np.array_equal(hard[:, : code.transmitted], tx)  # punctured bits excluded
    assert iterations.max() <= 50
    # One word through the scalar API gives the same answer.
    bits, ok, used, bad = ldpc.decode(llr[0], code)
    assert ok and bad == 0 and used == iterations[0] and np.array_equal(bits, hard[0])
    # The noisy channel had real errors for the decoder to fix.
    assert (np.sign(llr) < 0).astype(np.uint8).tolist() != tx.tolist()


def test_a_clean_codeword_needs_no_iterations() -> None:
    code = _code("IEEE 802.11n n=648 r1/2")
    u = _messages(code, 1, seed=1)[0]
    word = ldpc.encode(code, u)
    _, converged, iterations, unsat = ldpc.decode(10.0 * (1.0 - 2.0 * word), code)
    assert converged and iterations == 0 and unsat == 0


def test_decoding_fails_honestly_at_very_low_snr() -> None:
    for name in ("IEEE 802.11n n=648 r1/2", "CCSDS TM k=1024 r4/5"):
        code = _code(name)
        u = _messages(code, 4, seed=3)
        llr = _llr(ldpc.encode(code, u), -3.0, code.k / code.transmitted, np.random.default_rng(4))
        hard, converged, iterations, unsat = ldpc.decode_many(llr, code, max_iter=25)
        assert not converged.any()
        assert (unsat > 0).all() and (iterations == 25).all()
        assert not np.array_equal(hard[:, : code.k], u)
    # Pure noise never produces a code word either.
    noise = np.random.default_rng(9).standard_normal((4, code.transmitted))
    assert not ldpc.decode_many(noise, code, max_iter=25)[1].any()


def test_punctured_columns_are_erasures_and_full_length_input_is_accepted() -> None:
    code = _code("CCSDS TM k=1024 r2/3")
    u = _messages(code, 3, seed=8)
    llr = _llr(ldpc.encode(code, u), 3.5, code.k / code.transmitted, np.random.default_rng(9))
    padded = np.hstack([llr, np.zeros((3, code.punctured))])
    a = ldpc.decode_many(llr, code)
    b = ldpc.decode_many(padded, code)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[2], b[2])
    with pytest.raises(ValueError):
        ldpc.decode(np.zeros(code.transmitted + 1), code)
    # An unpunctured code takes exactly n, and only n.
    with pytest.raises(ValueError):
        ldpc.decode(np.zeros(647), _code("IEEE 802.11n n=648 r1/2"))


def test_llr_sign_convention_matches_viterbi() -> None:
    code = _code("CCSDS TC n=128 k=64")
    word = ldpc.encode(code, _messages(code, 1, seed=2)[0])
    hard = ldpc.decode(5.0 * (1.0 - 2.0 * word), code)[0]  # +LLR is bit 0, as in dsp.fec.viterbi
    assert np.array_equal(hard, word)
    assert not np.array_equal(ldpc.decode(-5.0 * (1.0 - 2.0 * word), code)[0], word)


# -- syndrome and alignment ----------------------------------------------------------------------


def test_random_bits_never_satisfy_the_syndrome() -> None:
    rng = np.random.default_rng(31)
    for name in ("IEEE 802.11n n=648 r1/2", "CCSDS TC n=512 k=256", "CCSDS TM k=1024 r1/2"):
        code = _code(name)
        words = rng.integers(0, 2, (20, code.n), dtype=np.uint8)
        assert abs(ldpc.syndrome_rate(words, code) - 0.5) < 0.04
        assert all(ldpc.syndrome(w, code).any() for w in words)


def test_the_syndrome_needs_the_full_word_of_a_punctured_code() -> None:
    code = _code("CCSDS TM k=1024 r4/5")
    with pytest.raises(ValueError, match="punctured"):
        ldpc.syndrome_rate(np.zeros(code.transmitted, np.uint8), code)
    with pytest.raises(ValueError):
        ldpc.syndrome(np.zeros(code.transmitted, np.uint8), code)


def _stream(code: LdpcCode, offset: int, words: int, ebn0: float, seed: int) -> NDArray[np.float64]:
    """`offset` random bits, then `words` consecutive transmitted code words, as noisy LLRs."""
    rng = np.random.default_rng(seed)
    bits = np.concatenate(
        [
            rng.integers(0, 2, offset, dtype=np.uint8),
            ldpc.encode(code, _messages(code, words, seed + 1)).ravel(),
        ]
    )
    return _llr(bits, ebn0, code.k / code.transmitted, rng)


def test_find_alignment_recovers_a_known_offset_by_hard_syndrome() -> None:
    code = _code("IEEE 802.11n n=648 r1/2")
    stream = _stream(code, offset=123, words=6, ebn0=4.5, seed=40)
    found = ldpc.find_alignment(stream, code, codewords=4)
    assert found.method == "syndrome" and found.hypotheses == 648 and found.codewords == 4
    assert found.found and found.offset == 123
    assert found.rate < found.threshold < 0.5
    # A noisy but unshuffled stream scores 0 only when clean; here some checks still fail.
    assert 0.0 <= found.rate < 0.35


def test_find_alignment_abstains_on_shuffled_bits() -> None:
    code = _code("IEEE 802.11n n=648 r1/2")
    stream = _stream(code, offset=123, words=6, ebn0=4.5, seed=40)
    shuffled = np.random.default_rng(41).permutation(stream)
    result = ldpc.find_alignment(shuffled, code, codewords=4)
    assert not result.found
    assert result.rate > result.threshold  # nothing beat chance over all 648 offsets
    assert result.rate > 0.4


def test_find_alignment_on_a_punctured_code_decodes_each_offset() -> None:
    code = _code("CCSDS TM k=1024 r4/5")
    stream = _stream(code, offset=77, words=3, ebn0=4.5, seed=50)
    found = ldpc.find_alignment(stream, code, codewords=2)
    assert found.method == "decode" and found.hypotheses == code.transmitted
    assert found.found and found.offset == 77 and found.rate == 0.0
    shuffled = np.random.default_rng(51).permutation(stream)
    assert not ldpc.find_alignment(shuffled, code, codewords=2).found


def test_find_alignment_needs_at_least_one_scannable_block() -> None:
    code = _code("CCSDS TC n=128 k=64")
    with pytest.raises(ValueError, match="at least"):
        ldpc.find_alignment(np.zeros(2 * code.n - 2), code)
    # Just enough for one code word at every offset: scans one block, not the four asked for.
    short = ldpc.find_alignment(np.zeros(2 * code.n - 1), code, codewords=4)
    assert short.codewords == 1
