"""The known-system catalogue and the Match stage against exact ground truth (PLAN M6): POCSAG
transmissions from dsp.synth (written independently of the decoder), CCSDS frames through the
chain, and the cases where nothing may be claimed."""

import math
from typing import Any

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from dsp.analyse import analyse
from dsp.detect import Detection, detect
from dsp.evidence import EvidenceLevel
from dsp.report import DetectionReport
from dsp.synth.chain import Scene, SignalSpec, generate
from dsp.synth.systems import (
    POCSAG_IDLE,
    POCSAG_SYNC,
    Dsc,
    Navtex,
    Pocsag,
    dsc_symbol_bits,
    pocsag_codeword,
    pocsag_text_words,
)
from dsp.systems import ccir476, dsc, pocsag
from dsp.systems.catalogue import CATALOGUE
from dsp.systems.match import MATCH_ALPHA, Candidate, Findings, holm, match

NOISE_DB = -20.0
ALPHA = MATCH_ALPHA
PAGES = ((1234567, 3, "HELLO SANKET"), (42, 3, "SECOND PAGE ACROSS BATCHES, LONGER TEXT HERE"))


class Memory:
    def __init__(self, x: Any) -> None:
        self.x = np.asarray(x)
        self.num_samples = len(self.x)

    def read(self, start: int, count: int) -> Any:
        return self.x[start : start + count]


def _pocsag_bits(pages: Any = PAGES, needed: int = 6000, corrupt: float = 0.0) -> Any:
    rng = np.random.default_rng(3)
    return Pocsag(pages=pages, corrupt=corrupt).stream(needed, rng)[2]


# --- the catalogue ---------------------------------------------------------------------------


def test_catalogue_entries_are_complete_and_unique() -> None:
    assert CATALOGUE.version
    ids = [e.id for e in CATALOGUE.entries]
    assert len(ids) == len(set(ids)) >= 2
    for e in CATALOGUE.entries:
        assert e.specification and e.licence and e.modulations and e.frame_check
        assert e.check in {"pocsag", "ccsds-tm", "ccsds-ldpc", "navtex", "dsc", "ais"}


def test_holm_steps_down_and_stops_at_the_first_failure() -> None:
    a = 0.01
    # sorted: 1e-9 against a/3, 0.004 against a/2, 0.5 against a
    assert holm([1e-9, 0.5, 0.004], a) == pytest.approx([a / 3, a, a / 2])
    # 1e-9 passes a/3, 0.2 fails a/2 and stops the walk, so 0.3 is tested against nothing
    assert holm([0.2, 1e-9, 0.3], a) == pytest.approx([a / 2, a / 3, 0.0])
    assert holm([], a) == []


# --- POCSAG codewords ------------------------------------------------------------------------


def test_the_standards_own_codewords_pass_the_check() -> None:
    """The synchronisation and idle codewords are constants of ITU-R M.584, so this tests the
    generator polynomial and parity against something we did not derive."""
    w = np.array([POCSAG_SYNC, POCSAG_IDLE], np.uint64)
    assert pocsag.check(w).all()
    assert pocsag.SYNC.value == POCSAG_SYNC and pocsag.IDLE == POCSAG_IDLE


@given(st.integers(0, (1 << 21) - 1))
@settings(max_examples=200, deadline=None)
def test_encoder_and_checker_agree_and_any_one_to_three_flips_are_caught(data: int) -> None:
    word = pocsag_codeword(data)
    assert word == pocsag.encode_word(data)  # the synth's encoder and the decoder's agree
    assert pocsag.check(np.array([word], np.uint64)).all()
    for bit in range(32):  # extended BCH(32,21) has minimum distance 6
        flipped = np.array([word ^ (1 << bit)], np.uint64)
        assert not pocsag.check(flipped).any()
    rng = np.random.default_rng(data)
    for _ in range(20):
        bits = rng.choice(32, size=int(rng.integers(2, 4)), replace=False)
        assert not pocsag.check(np.array([word ^ sum(1 << int(b) for b in bits)], np.uint64)).any()


def test_a_random_word_passes_with_probability_two_to_the_minus_eleven() -> None:
    rng = np.random.default_rng(1)
    words = rng.integers(0, 1 << 32, 400_000, dtype=np.uint64)
    rate = float(pocsag.check(words).mean())
    assert rate == pytest.approx(2.0**-11, rel=0.25)


# --- POCSAG scan -----------------------------------------------------------------------------


def test_scan_reads_back_exactly_the_transmitted_pages() -> None:
    found = pocsag.scan(_pocsag_bits()[37:])  # the recording starts mid-preamble
    assert found is not None and not found.inverted
    assert found.recurrences >= 5
    assert found.valid > 0.8 * found.codewords  # the preambles between transmissions fail
    assert found.p_value < 1e-100
    texts = {(p.address, p.text) for p in found.pages}
    assert texts == {(ric, text) for ric, _, text in PAGES}
    assert {p.function for p in found.pages} == {3}


def test_scan_reads_an_inverted_stream() -> None:
    found = pocsag.scan(1 - _pocsag_bits()[11:])
    assert found is not None and found.inverted
    assert {p.text for p in found.pages} == {text for _, _, text in PAGES}


def test_a_page_with_a_corrupted_codeword_is_not_rendered() -> None:
    bits = _pocsag_bits(pages=((5, 3, "A LONG ENOUGH MESSAGE TO NEED SEVERAL WORDS"),)).copy()
    first = pocsag.scan(bits)
    assert first is not None
    # Page 5 is in frame 5, so its address sits in codeword 10 of the batch and its message
    # words follow: flip one bit inside the second of them (codeword 12 after the sync word).
    bits[first.batches[0].start_bit + 32 * 12 + 5] ^= 1
    again = pocsag.scan(bits)
    assert again is not None
    assert again.pages[0].text is None and again.pages[1].text is not None
    assert again.valid == first.valid - 1


def test_numeric_and_tone_pages_are_found_but_not_rendered() -> None:
    found = pocsag.scan(_pocsag_bits(pages=((900, 0, "1234567890" * 4),)))
    assert found is not None and found.pages[0].function == 0 and found.pages[0].text is None


@pytest.mark.parametrize("kind", ["random", "zeros", "ones", "preamble"])
def test_scan_claims_nothing_on_streams_without_the_synchronisation_codeword(kind: str) -> None:
    rng = np.random.default_rng(9)
    bits = {
        "random": rng.integers(0, 2, 30_000).astype(np.uint8),
        "zeros": np.zeros(30_000, np.uint8),  # all-zero codewords are valid BCH words
        "ones": np.ones(30_000, np.uint8),
        "preamble": np.tile(np.array([1, 0], np.uint8), 15_000),
    }[kind]
    assert pocsag.scan(bits) is None


def test_right_synchronisation_but_random_codewords_is_not_verified() -> None:
    """A near miss: the synchronisation codeword every 544 bits, everything else random."""
    rng = np.random.default_rng(4)
    sync = np.array([(POCSAG_SYNC >> (31 - i)) & 1 for i in range(32)], np.uint8)
    stream = np.concatenate(
        [np.concatenate([sync, rng.integers(0, 2, 512).astype(np.uint8)]) for _ in range(20)]
    )
    found = pocsag.scan(stream)
    assert found is not None and found.recurrences >= 10
    assert found.valid <= 2 and found.p_value > 1e-3  # a chance pass or two, nothing more
    result = match([Candidate("only", Findings("2FSK", 1200.0, 5.0), stream)], None, ALPHA)
    assert result.verified is None
    assert result.stage.level is EvidenceLevel.UNKNOWN


def test_scan_survives_scattered_bit_errors() -> None:
    found = pocsag.scan(_pocsag_bits(pages=PAGES * 3, needed=20_000, corrupt=0.004))
    assert found is not None and found.p_value < 1e-100
    assert 0.4 < found.valid / found.codewords < 0.95  # errors cost codewords, never invent them


def test_text_words_round_trip_through_the_decoder() -> None:
    words = np.array(pocsag_text_words("PAGE 7/OK"), np.uint64)
    assert pocsag.check(words).all()
    data = [int(w) >> 11 & 0xFFFFF for w in words]
    assert pocsag._text(data) == "PAGE 7/OK"  # pyright: ignore[reportPrivateUsage]


# --- the Match stage on candidates -----------------------------------------------------------


def _candidate(bits: Any, modulation: str = "2FSK", rate: float | None = 1200.0) -> Candidate:
    return Candidate("c", Findings(modulation, rate, 6.0 if rate else None), bits)


def test_match_verifies_pocsag_by_its_own_check_with_a_reencode_proof() -> None:
    result = match([_candidate(_pocsag_bits())], None, ALPHA)
    assert result.verified is not None and result.verified.id == "pocsag"
    system = result.stage.parameters[0]
    assert system.level is EvidenceLevel.VERIFIED and system.value == "POCSAG paging"
    assert system.proof is not None and system.proof.kind == "reencode"
    assert result.stage.level is EvidenceLevel.VERIFIED
    pages = next(p for p in result.stage.parameters if p.id == "pages")
    assert pages.level is EvidenceLevel.HYPOTHESIS and pages.convention  # listed for review
    assert any("HELLO SANKET" in line for line in pages.evidence)
    assert result.frames and all(f.sync_word == "0x7CD215D8" for f in result.frames)
    assert sum(f.crc == "pass" for f in result.frames) >= 5
    assert result.tried >= 1
    assert any(r.layer == "Match" and r.outcome == "accepted" for r in result.rows)


def test_match_needs_no_sample_rate_for_the_check() -> None:
    result = match([_candidate(_pocsag_bits(), rate=None)], None, ALPHA)
    assert result.verified is not None
    shown = " ".join(result.stage.parameters[0].evidence)
    assert "no sample rate" in shown  # the rate comparison is stated as not made


@pytest.mark.parametrize("rate", [512.0, 1200.0, 2400.0, 1215.0])
def test_match_accepts_the_catalogued_rates_within_tolerance(rate: float) -> None:
    assert match([_candidate(_pocsag_bits(), rate=rate)], None, ALPHA).verified is not None


@pytest.mark.parametrize(
    ("modulation", "rate", "why"),
    [
        ("QPSK", 1200.0, "modulation"),
        ("2FSK", 300.0, "symbol rate"),
        ("2FSK", 4800.0, "symbol rate"),  # 9,600 Bd is AIS's, whose check would run and fail
    ],
)
def test_match_does_not_run_a_check_on_bits_demodulated_for_something_else(
    modulation: str, rate: float, why: str
) -> None:
    """The bits are POCSAG's, but the blind findings say another signal: conflicts are listed and
    the check is not run (a pass there would prove nothing about this recording)."""
    result = match([_candidate(_pocsag_bits(), modulation, rate)], None, ALPHA)
    assert result.verified is None
    assert result.stage.level is EvidenceLevel.UNKNOWN
    assert any(why in r.reason for r in result.rows if r.outcome == "rejected")
    # No POCSAG check ran, and CCSDS had no chain to read; a QPSK candidate does get the six
    # CCSDS TM LDPC checks (it fits that system by parameters), which find nothing in these bits.
    assert not any(r.candidate.startswith("POCSAG") and r.p_value for r in result.rows)
    assert result.tried == (6 if modulation == "QPSK" else 0)


def test_match_with_too_few_bits_says_consistent_and_does_not_verify() -> None:
    result = match([_candidate(_pocsag_bits()[:800])], None, ALPHA)
    assert result.verified is None
    assert result.stage.level is EvidenceLevel.HYPOTHESIS
    system = result.stage.parameters[0]
    assert system.level is EvidenceLevel.HYPOTHESIS and "consistent with POCSAG" in str(
        system.value
    )


def test_match_unknown_names_every_entry_and_why() -> None:
    rng = np.random.default_rng(2)
    result = match([_candidate(rng.integers(0, 2, 8000).astype(np.uint8))], None, ALPHA)
    system = result.stage.parameters[0]
    assert system.level is EvidenceLevel.UNKNOWN and system.value is None
    assert system.resolve_hint
    shown = " ".join(system.evidence)
    assert "POCSAG paging" in shown and "CCSDS telemetry coding" in shown


def test_match_holm_counts_every_check_and_no_random_stream_verifies() -> None:
    rng = np.random.default_rng(6)
    for _ in range(50):
        bits = rng.integers(0, 2, 12_000).astype(np.uint8)
        assert match([_candidate(bits)], None, ALPHA).verified is None


def test_sync_with_a_constant_body_is_not_verified() -> None:
    """All-zero and all-one words are valid BCH words, so a constant body passes every codeword
    while being nothing like a random word: they are not counted, and nothing is claimed."""
    sync = np.array([(POCSAG_SYNC >> (31 - i)) & 1 for i in range(32)], np.uint8)
    for fill in (0, 1):
        body = np.full(512, fill, np.uint8)
        stream = np.tile(np.concatenate([sync, body]), 4)
        result = match([_candidate(stream)], None, ALPHA)
        assert result.verified is None, fill
        assert result.stage.level is EvidenceLevel.UNKNOWN


def test_the_consistent_with_claim_keeps_its_caveats_and_the_failures() -> None:
    short = _candidate(_pocsag_bits()[:800], rate=None)
    noise = _candidate(np.random.default_rng(2).integers(0, 2, 8000).astype(np.uint8), rate=1200.0)
    result = match([short, noise], None, ALPHA)
    system = result.stage.parameters[0]
    assert system.level is EvidenceLevel.HYPOTHESIS
    shown = " ".join(system.evidence)
    assert "no sample rate" in shown  # the rate comparison that was not made
    assert "recurs one batch apart" in shown  # and the candidate that was checked and failed


def test_ccsds_fit_names_the_exact_code_and_outer_code() -> None:
    entry = next(e for e in CATALOGUE.entries if e.id == "ccsds-tm")
    from dsp.systems.match import fit

    ok = Findings("QPSK", code="Conv K=7 r½ (171,133)₈", outer="RS(255,223) CCSDS")
    assert fit(entry, ok)[0] == []
    assert fit(entry, Findings("QPSK", code="Conv K=7 r2/3 punctured (171,133)₈"))[0] == []
    assert fit(entry, Findings("QPSK", code="Conv K=7 r1/3 (171,133,165)₈"))[0]  # not CCSDS's
    assert fit(entry, Findings("QPSK", code="Conv K=7 r½ (133,171)₈"))[0]
    assert fit(entry, Findings("QPSK", code="Uncoded", outer="RS(204,188)"))[0]


def test_a_polarity_choice_costs_a_factor_of_two_in_the_p_value() -> None:
    both = pocsag.scan(_pocsag_bits(pages=PAGES * 3, needed=20_000, corrupt=0.2))
    assert both is None or both.p_value >= 2 * 2.0**-11  # never better than one polarity alone


# --- SITOR-B / NAVTEX ------------------------------------------------------------------------

NAVTEX = Navtex()


def _navtex_bits(needed: int = 3000, corrupt: float = 0.0, navtex: Navtex = NAVTEX) -> Any:
    return navtex.stream(needed, np.random.default_rng(1))[2]


def test_the_ccir476_tables_are_complete_four_of_seven_codes() -> None:
    for table in (ccir476.LETTERS, ccir476.FIGURES):
        assert len(table) == 35 and all(code.bit_count() == 4 for code in table)
    assert set(ccir476.LETTERS) == set(ccir476.FIGURES)
    # The control codes agree with the signals the standard gives them: alpha, beta, repeat.
    assert (ccir476.SIA, ccir476.SIB, ccir476.RPT) == (0b0001111, 0b0110011, 0b1100110)
    assert ccir476.LETTERS[ccir476.SIA] == "SIA" and ccir476.FIGURES[ccir476.RPT] == "RPT"
    # Only the controls and punctuation differ between the sets; both shifts are in both.
    assert ccir476.LETTERS[ccir476.LTRS] == ccir476.FIGURES[ccir476.LTRS] == "LTRS"


@pytest.mark.parametrize("shift", [0, 3, 13])
def test_scan_reads_back_exactly_the_transmitted_message(shift: int) -> None:
    found = ccir476.scan(_navtex_bits()[shift:])
    assert found is not None and not found.inverted and found.bit_order == "as tabulated"
    assert found.p_value < 1e-100 and found.erased == 0
    first = found.messages[0]
    assert (first.station, first.subject, first.serial) == ("E", "A", "12")
    assert first.body == NAVTEX.text and first.complete
    assert {m.body for m in found.messages} == {NAVTEX.text}


def test_scan_reads_an_inverted_stream_and_says_so() -> None:
    found = ccir476.scan(1 - _navtex_bits()[5:])
    assert found is not None and found.inverted
    assert found.messages[0].body == NAVTEX.text


def test_message_positions_point_at_the_characters_in_the_stream() -> None:
    bits = _navtex_bits()
    found = ccir476.scan(bits)
    assert found is not None
    g = ccir476.groups(bits, found.offset)
    m = found.messages[0]
    z = ccir476.LETTERS  # the message starts at its first Z of ZCZC
    assert z[int(g[(m.start_bit - found.offset) // 7])] == "Z"


def test_a_damaged_first_copy_is_recovered_from_its_repetition() -> None:
    """The point of the time diversity: corrupt a first transmission, read the character from its
    repetition five slots later."""
    bits = _navtex_bits().copy()
    found = ccir476.scan(bits)
    assert found is not None
    slot = 2 * (10 + 12) + (1 - found.repeat_parity)  # a first-copy slot well inside the message
    bits[found.offset + 7 * slot + 2] ^= 1
    again = ccir476.scan(bits)
    assert again is not None and again.erased == 0
    assert again.messages[0].body == NAVTEX.text and again.messages[0].complete


def test_a_character_with_both_copies_damaged_is_marked_not_guessed() -> None:
    bits = _navtex_bits().copy()
    found = ccir476.scan(bits)
    assert found is not None
    d = 2 * (10 + 12) + (1 - found.repeat_parity)
    for slot in (d, d + 5):
        bits[found.offset + 7 * slot + 2] ^= 1
    again = ccir476.scan(bits)
    assert again is not None and again.erased == 1
    assert "?" in again.text and not again.messages[0].complete


def test_reversed_bit_order_is_noticed_from_the_headers() -> None:
    bits = _navtex_bits()
    n = len(bits) // 7 * 7
    reversed_chars = bits[:n].reshape(-1, 7)[:, ::-1].ravel()
    found = ccir476.scan(reversed_chars)
    assert found is not None and found.bit_order == "reversed"
    assert found.messages[0].body == NAVTEX.text


def test_scattered_bit_errors_cost_characters_not_the_verdict() -> None:
    found = ccir476.scan(_navtex_bits(needed=20_000, corrupt=0.0))
    noisy = Navtex(corrupt=0.004).stream(20_000, np.random.default_rng(2))[2]
    hit = ccir476.scan(noisy)
    assert found is not None and hit is not None and hit.p_value < 1e-100
    assert 0 < hit.agree < found.agree  # errors remove agreeing pairs, never invent them


@pytest.mark.parametrize(
    "kind", ["random", "zeros", "constant", "alternating", "period35", "phasing"]
)
def test_the_diversity_check_claims_nothing_without_repeated_characters(kind: str) -> None:
    rng = np.random.default_rng(3)
    word = np.array([0, 0, 0, 1, 1, 1, 1], np.uint8)
    phasing = np.concatenate([np.tile(np.array([0, 1, 1, 0, 0, 1, 1], np.uint8), 1), word])
    bits = {
        "random": rng.integers(0, 2, 30_000).astype(np.uint8),
        "zeros": np.zeros(30_000, np.uint8),
        "constant": np.tile(word, 3000),  # a valid character, repeated: not evidence
        "alternating": np.tile(np.array([1, 0], np.uint8), 15_000),
        "period35": np.tile(rng.integers(0, 2, 35).astype(np.uint8), 800),  # equal five slots on
        "phasing": np.tile(phasing, 1500),  # alpha and beta alternating: copies never agree
    }[kind]
    assert ccir476.scan(bits) is None


def test_random_streams_are_not_matched_across_many_seeds() -> None:
    rng = np.random.default_rng(10)
    for _ in range(300):
        found = ccir476.scan(rng.integers(0, 2, 12_000).astype(np.uint8))
        # a few random streams clear the minimum (8 varied agreeing pairs); none is significant
        assert found is None or found.p_value > MATCH_ALPHA


def _navtex_candidate(bits: Any, rate: float | None = 100.0, modulation: str = "2FSK") -> Candidate:
    return Candidate("c", Findings(modulation, rate, 1.0 if rate else None), bits)


def test_match_verifies_navtex_with_the_messages_listed_for_review() -> None:
    result = match([_navtex_candidate(_navtex_bits())], None, ALPHA)
    assert result.verified is not None and result.verified.id == "navtex"
    system = result.stage.parameters[0]
    assert system.level is EvidenceLevel.VERIFIED and system.proof is not None
    assert system.proof.kind == "reencode"
    messages = next(p for p in result.stage.parameters if p.id == "messages")
    assert messages.level is EvidenceLevel.HYPOTHESIS and messages.convention
    assert any(NAVTEX.text in line and line.startswith("EA12") for line in messages.evidence)
    assert len(messages.evidence) == 1  # the repeats of one message are listed once
    assert result.frames and all(f.sync_word == "ZCZC" and f.crc == "pass" for f in result.frames)


@pytest.mark.parametrize(
    ("modulation", "rate"), [("2FSK", 1200.0), ("2FSK", 50.0), ("QPSK", 100.0)]
)
def test_navtex_is_not_checked_against_bits_demodulated_for_another_signal(
    modulation: str, rate: float
) -> None:
    result = match([_navtex_candidate(_navtex_bits(), rate, modulation)], None, ALPHA)
    assert result.verified is None and result.stage.level is EvidenceLevel.UNKNOWN


def test_match_keeps_pocsag_and_navtex_apart() -> None:
    assert match([_candidate(_pocsag_bits(), rate=100.0)], None, ALPHA).verified is None
    bits = _navtex_bits()
    assert match([_navtex_candidate(bits, rate=1200.0)], None, ALPHA).verified is None


# --- MF/HF DSC -------------------------------------------------------------------------------

DSC = Dsc()


def _dsc_bits(needed: int = 5000, call: Dsc = DSC) -> Any:
    return call.stream(needed, np.random.default_rng(1))[2]


def test_dsc_characters_follow_the_recommendations_own_examples() -> None:
    """Annex 1 section 1.1: a BYY check (3 B elements) and a YYB check (6 B elements)."""
    # symbol 0x0F: info bits (LSB first) 1111000 -> 3 zeros -> check 011 = BYY
    assert dsc_symbol_bits(0x0F).tolist() == [1, 1, 1, 1, 0, 0, 0, 0, 1, 1]
    # symbol 1: info 1000000 -> 6 zeros -> check 110 = YYB
    assert dsc_symbol_bits(1).tolist() == [1, 0, 0, 0, 0, 0, 0, 1, 1, 0]
    for symbol in range(128):  # every symbol's own check passes the decoder's rule
        _, valid = dsc.groups(dsc_symbol_bits(symbol), 0)
        assert valid.all()


@pytest.mark.parametrize("shift", [0, 4, 17])
def test_dsc_scan_reads_back_the_exact_call_and_its_ecc(shift: int) -> None:
    found = dsc.scan(_dsc_bits()[shift:])
    assert found is not None and not found.inverted and found.p_value < 1e-100
    assert found.erased <= 60  # only the dot pattern's bits are not characters
    call = found.calls[0]
    assert call.format == 120 and call.format_name == "individual station"
    assert call.eos == 127 and call.complete and call.ecc_ok is True
    assert [s for s in call.content if s is not None] == DSC.symbols()[2:-4]
    assert call.first_field == DSC.address
    assert all(c.ecc_ok for c in found.calls)


def test_dsc_scan_reads_an_inverted_stream() -> None:
    found = dsc.scan(1 - _dsc_bits()[3:])
    assert found is not None and found.inverted and found.calls[0].ecc_ok is True


def test_a_wrong_error_check_character_is_reported_not_hidden() -> None:
    bits = _dsc_bits().copy()
    found = dsc.scan(bits)
    assert found is not None
    # Replace the ECC's two copies (DX and RX) by another valid character: copies and check bits
    # still agree, so the stream is DSC, but the call's parity is wrong.
    symbols = DSC.symbols()
    ecc_slot_dx = 2 * (14 // 2 + len(symbols) - 1)  # first transmission of the ECC, in slots
    bad = dsc_symbol_bits((symbols[-1] + 1) % 128)
    for slot in (ecc_slot_dx, ecc_slot_dx + 5):
        at = found.offset + 200 % 10 + 10 * slot
        del at  # positions differ per transmission; rebuild the stream instead
    altered = Dsc(format=120, address=DSC.address, eos=127).transmission().copy()
    start = 200 + 10 * (14 + 2 * (len(symbols) - 1))
    altered[start : start + 10] = bad
    tail = 200 + 10 * (14 + 2 * (len(symbols) - 1) + 5)
    altered[tail : tail + 10] = bad
    again = dsc.scan(np.tile(altered, 8))
    assert again is not None
    assert again.calls and again.calls[0].ecc_ok is False


def test_a_damaged_dsc_character_is_read_from_its_repetition() -> None:
    bits = _dsc_bits().copy()
    found = dsc.scan(bits)
    assert found is not None
    bits[found.offset + 10 * (2 * 12 + (1 - found.repeat_parity)) + 1] ^= 1
    again = dsc.scan(bits)
    assert again is not None and again.calls[0].complete and again.calls[0].ecc_ok is True
    assert again.erased <= found.erased


@pytest.mark.parametrize("kind", ["random", "zeros", "phasing", "constant", "navtex", "pocsag"])
def test_the_dsc_check_claims_nothing_on_other_streams(kind: str) -> None:
    rng = np.random.default_rng(5)
    phasing = np.tile(np.concatenate([dsc_symbol_bits(125), dsc_symbol_bits(111)]), 800)
    bits = {
        "random": rng.integers(0, 2, 30_000).astype(np.uint8),
        "zeros": np.zeros(30_000, np.uint8),
        "phasing": phasing,  # 125 in DX, 111 in RX: valid characters that never agree
        "constant": np.tile(dsc_symbol_bits(125), 3000),
        "navtex": _navtex_bits(needed=20_000),
        "pocsag": _pocsag_bits(needed=20_000),
    }[kind]
    found = dsc.scan(bits)
    assert found is None or found.p_value > MATCH_ALPHA


def test_navtex_and_dsc_do_not_verify_each_others_streams() -> None:
    seen = ccir476.scan(_dsc_bits(needed=20_000))
    assert seen is None or seen.p_value > MATCH_ALPHA
    # Every entry runs on every candidate: NAVTEX's bits verify NAVTEX and only NAVTEX.
    result = match([_dsc_candidate(_navtex_bits(needed=20_000))], None, ALPHA)
    assert result.verified is not None and result.verified.id == "navtex"


def _dsc_candidate(bits: Any, rate: float | None = 100.0, modulation: str = "2FSK") -> Candidate:
    return Candidate("c", Findings(modulation, rate, 1.0 if rate else None), bits)


def test_match_verifies_dsc_with_its_calls_and_ecc_listed() -> None:
    result = match([_dsc_candidate(_dsc_bits())], None, ALPHA)
    assert result.verified is not None and result.verified.id == "dsc"
    system = result.stage.parameters[0]
    assert system.level is EvidenceLevel.VERIFIED and system.proof is not None
    assert system.proof.kind == "reencode"
    assert any("Error-check character matches" in line for line in system.evidence)
    calls = next(p for p in result.stage.parameters if p.id == "calls")
    assert calls.level is EvidenceLevel.HYPOTHESIS and calls.convention
    assert len(calls.evidence) == 1 and "individual station" in calls.evidence[0]
    assert result.frames and all(f.crc == "pass" for f in result.frames)


def test_dsc_is_not_checked_on_bits_demodulated_for_another_signal() -> None:
    for modulation, rate in (("2FSK", 1200.0), ("2FSK", 50.0), ("QPSK", 100.0)):
        result = match([_dsc_candidate(_dsc_bits(), rate, modulation)], None, ALPHA)
        assert result.verified is None


# --- end to end through detect and analyse ---------------------------------------------------


def _detect_main(samples: Any) -> tuple[Memory, Detection]:
    source = Memory(samples)
    detections = detect(source, real=False).detections
    assert detections, "the signal must be detected"
    return source, max(detections, key=lambda d: (d.stop - d.start) * (d.high - d.low))


def _stage(report: DetectionReport, stage_id: str) -> Any:
    return next(s for s in report.stages if s.id == stage_id)


SPS = 8
FS = 1200.0 * SPS


def _fsk_scene(esn0: float, spec_extra: dict[str, Any], seed: int = 5) -> Any:
    power = NOISE_DB + esn0 - 10 * math.log10(SPS)
    spec = SignalSpec(
        modulation="2fsk", sps=SPS, fsk_index=1.0, power_db=power, start=2000, **spec_extra
    )
    return generate(
        Scene(samples=1 << 17, signals=(spec,), noise_db=NOISE_DB, sample_rate=FS), seed
    )


def test_a_pocsag_recording_is_verified_by_match_and_its_pages_read_back() -> None:
    g = _fsk_scene(15.0, {"frame": None, "system": Pocsag(pages=PAGES), "duration": 120_000})
    source, main = _detect_main(g.samples)
    report = analyse(source, main, sample_rate=FS)
    assert report.level is EvidenceLevel.VERIFIED and report.label == "2FSK"
    match_stage = _stage(report, "match")
    system = next(p for p in match_stage.parameters if p.id == "system")
    assert system.level is EvidenceLevel.VERIFIED and system.value == "POCSAG paging"
    assert system.proof is not None and system.proof.kind == "reencode"
    # The system's proof settles the demodulation it ran on; the blind FEC search still stands.
    assert _stage(report, "classify").level is EvidenceLevel.VERIFIED
    assert _stage(report, "fec").level is EvidenceLevel.UNKNOWN
    pages = next(p for p in match_stage.parameters if p.id == "pages")
    shown = " ".join(pages.evidence)
    for _, _, text in PAGES:
        assert f'"{text}"' in shown
    assert report.frames and report.frames[0].sync_word == "0x7CD215D8"
    assert sum(f.crc == "pass" for f in report.frames) >= 0.6 * len(report.frames)
    assert report.search is not None and report.search.match_tried >= 1
    assert any(r.layer == "Match" and r.outcome == "accepted" for r in report.search.rows)
    assert "POCSAG paging" in report.headline


def test_pocsag_is_not_claimed_for_a_crc_framed_fsk_signal() -> None:
    """The chain decodes this one on its own CRC; Match finds no POCSAG in it and says so."""
    g = _fsk_scene(15.0, {"duration": 120_000})
    source, main = _detect_main(g.samples)
    report = analyse(source, main, sample_rate=FS)
    assert report.level is EvidenceLevel.VERIFIED  # by the frame CRC
    system = next(p for p in _stage(report, "match").parameters if p.id == "system")
    assert system.level is EvidenceLevel.UNKNOWN and system.value is None
    assert report.search is not None
    assert not any(r.layer == "Match" and r.outcome == "accepted" for r in report.search.rows)


def _psk_report(**spec_extra: Any) -> DetectionReport:
    power = NOISE_DB + 15.0 - 10 * math.log10(SPS)
    spec = SignalSpec(
        modulation="qpsk", sps=SPS, power_db=power, start=10_000, duration=110_000, **spec_extra
    )
    g = generate(
        Scene(samples=1 << 17, signals=(spec,), noise_db=NOISE_DB, sample_rate=48_000.0), 7
    )
    source, main = _detect_main(g.samples)
    return analyse(source, main, sample_rate=48_000.0)


def test_ccsds_framing_is_matched_and_verified_by_the_frame_check() -> None:
    report = _psk_report()
    assert report.level is EvidenceLevel.VERIFIED
    system = next(p for p in _stage(report, "match").parameters if p.id == "system")
    assert system.level is EvidenceLevel.VERIFIED and system.value == "CCSDS telemetry coding"
    assert system.proof is not None and system.proof.kind == "crc"
    header = next(p for p in _stage(report, "match").parameters if p.id == "tm_header")
    assert header.level is EvidenceLevel.VERIFIED and "version 0" in str(header.value)
    assert "CCSDS telemetry coding" in report.headline
    assert report.search is not None and report.search.match_tried >= 1


def test_a_ccsds_pseudo_randomiser_still_matches_but_g3ruh_does_not() -> None:
    ok = _psk_report(scrambler="CCSDS")
    assert next(p for p in _stage(ok, "match").parameters if p.id == "system").value == (
        "CCSDS telemetry coding"
    )
    other = _psk_report(scrambler="G3RUH")
    assert other.level is EvidenceLevel.VERIFIED  # the chain decodes it on its own
    system = next(p for p in _stage(other, "match").parameters if p.id == "system")
    assert system.level is EvidenceLevel.UNKNOWN
    assert "G3RUH" in " ".join(system.evidence)


def test_match_adds_a_stage_and_leaves_the_blind_stages_in_place() -> None:
    report = _psk_report()
    stages = {s.id: s for s in report.stages}
    assert {"detect", "estimate", "sync", "classify", "demod", "fec", "frame", "match"} <= set(
        stages
    )
    assert stages["frame"].level is EvidenceLevel.VERIFIED
    assert report.search is not None
    assert any(r.layer == "Framing" or r.layer == "FEC" for r in report.search.rows)


def test_a_verified_system_ends_the_blind_search_instead_of_running_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The blind code, interleaver and framing searches would only re-decode what the system's
    own proof already covers: none of them may run once Match has settled the signal."""

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a blind search ran after a known system was verified")

    for name in ("_blind_conv_cells", "_interleaver_cells", "_forney_cells", "_blind_block_cells"):
        monkeypatch.setattr(f"dsp.analyse.{name}", forbidden)
    monkeypatch.setattr("dsp.analyse._blind_frame_cells", forbidden)
    g = _fsk_scene(15.0, {"frame": None, "system": Pocsag(pages=PAGES), "duration": 100_000})
    source, main = _detect_main(g.samples)
    report = analyse(source, main, sample_rate=FS)
    system = next(p for p in _stage(report, "match").parameters if p.id == "system")
    assert system.level is EvidenceLevel.VERIFIED


def test_a_mirrored_pocsag_recording_with_no_sample_rate_is_verified_and_says_what_it_skipped() -> (
    None
):
    """Swapping I and Q mirrors the spectrum, which inverts every 2-FSK bit: the system's proof
    settles the bit mapping, and with no sample rate the rate comparison is stated as not made."""
    g = _fsk_scene(15.0, {"frame": None, "system": Pocsag(pages=PAGES), "duration": 100_000})
    source, main = _detect_main(np.conj(g.samples))
    report = analyse(source, main)  # no sample rate
    match_stage = _stage(report, "match")
    system = next(p for p in match_stage.parameters if p.id == "system")
    assert system.level is EvidenceLevel.VERIFIED
    assert "no sample rate" in " ".join(system.evidence)
    mapping = next(p for p in _stage(report, "demod").parameters if p.id == "bit_mapping")
    assert mapping.level is EvidenceLevel.VERIFIED and mapping.value == "upper tone = 0"


def test_a_random_fsk_recording_gets_no_system_through_the_whole_chain() -> None:
    g = _fsk_scene(15.0, {"frame": None, "duration": 100_000})  # random payload bits, no framing
    source, main = _detect_main(g.samples)
    report = analyse(source, main, sample_rate=FS)
    system = next(p for p in _stage(report, "match").parameters if p.id == "system")
    assert system.level is EvidenceLevel.UNKNOWN
    assert report.level is not EvidenceLevel.VERIFIED


def test_a_navtex_recording_is_verified_and_its_message_read_back_through_the_chain() -> None:
    power = NOISE_DB + 15.0 - 10 * math.log10(SPS)
    spec = SignalSpec(
        modulation="2fsk",
        sps=SPS,
        fsk_index=1.0,
        power_db=power,
        frame=None,
        system=NAVTEX,
        start=2000,
        duration=120_000,
    )
    rate = 100.0 * SPS
    g = generate(Scene(samples=1 << 17, signals=(spec,), noise_db=NOISE_DB, sample_rate=rate), 5)
    source, main = _detect_main(g.samples)
    report = analyse(source, main, sample_rate=rate)
    assert report.level is EvidenceLevel.VERIFIED and report.label == "2FSK"
    match_stage = _stage(report, "match")
    system = next(p for p in match_stage.parameters if p.id == "system")
    assert system.level is EvidenceLevel.VERIFIED and system.value == "NAVTEX (SITOR-B)"
    assert _stage(report, "classify").level is EvidenceLevel.VERIFIED  # settled by the proof
    messages = next(p for p in match_stage.parameters if p.id == "messages")
    assert messages.evidence == (f"EA12: {NAVTEX.text}",)
    assert report.frames and all(f.crc == "pass" for f in report.frames)
    assert "NAVTEX" in report.headline


def test_a_dsc_recording_is_verified_and_its_call_read_back_through_the_chain() -> None:
    power = NOISE_DB + 15.0 - 10 * math.log10(SPS)
    spec = SignalSpec(
        modulation="2fsk",
        sps=SPS,
        fsk_index=1.0,
        power_db=power,
        frame=None,
        system=DSC,
        start=2000,
        duration=120_000,
    )
    rate = 100.0 * SPS
    g = generate(Scene(samples=1 << 17, signals=(spec,), noise_db=NOISE_DB, sample_rate=rate), 5)
    source, main = _detect_main(g.samples)
    report = analyse(source, main, sample_rate=rate)
    assert report.level is EvidenceLevel.VERIFIED
    match_stage = _stage(report, "match")
    system = next(p for p in match_stage.parameters if p.id == "system")
    assert system.level is EvidenceLevel.VERIFIED and system.value == "MF/HF DSC"
    calls = next(p for p in match_stage.parameters if p.id == "calls")
    assert "individual station" in calls.evidence[0] and "ECC matches" in calls.evidence[0]
    assert f"first field {DSC.address}" in calls.evidence[0]
    assert report.frames and all(f.crc == "pass" for f in report.frames)


def test_dsc_polarity_is_unresolved_without_a_readable_call_and_says_so() -> None:
    """A complemented stream is also a valid stream (symbol s reads as 127 - s), so when no call
    can be read the polarity is only assumed, and Match's evidence says so."""
    odd = Dsc(format=100)  # not one of the Recommendation's format specifiers: no call reads
    found = dsc.scan(_dsc_bits(call=odd))
    assert found is not None and not found.calls and not found.polarity_read
    result = match([_dsc_candidate(_dsc_bits(call=odd))], None, ALPHA)
    assert result.verified is not None and result.verified.id == "dsc"
    shown = " ".join(result.stage.parameters[0].evidence)
    assert "polarity is not settled" in shown
    assert not any(p.id == "calls" for p in result.stage.parameters)
    # no call to show, but the copies agree, which is this system's frame check
    assert len(result.frames) == 1 and result.frames[0].sync_word == "DSC"
    assert result.frames[0].crc == "pass"


def test_a_matched_ccsds_stream_has_its_frame_table_split_at_the_primary_header() -> None:
    report = _psk_report()
    match_stage = _stage(report, "match")
    assert next(p for p in match_stage.parameters if p.id == "system").value == (
        "CCSDS telemetry coding"
    )
    frame = next(f for f in report.frames if f.crc == "pass")
    head = frame.header_hex.split(" ")
    assert len(head) == 6  # the primary header, where the unmatched table shows four bytes
    assert "".join(head) == frame.payload_hex[:12]
    assert len(frame.payload_hex) > 12  # the payload column still holds the whole frame
