"""The CCSDS TM LDPC (AR4JA) known system against exact ground truth (PLAN M6): streams from
`dsp.synth.systems.CcsdsLdpc` (marker, randomiser, codewords from the galois encoder, written
independently of the decoder) through the system's own check, and through `analyse`; near-misses
and noise that must not verify; the p-value arithmetic."""

import math
from typing import Any

import numpy as np
import pytest

from dsp.analyse import analyse
from dsp.detect import detect
from dsp.evidence import EvidenceLevel
from dsp.fec import ldpc
from dsp.report import DetectionReport
from dsp.scramble import CCSDS
from dsp.synth.chain import Scene, SignalSpec, generate
from dsp.synth.systems import CcsdsLdpc, ccsds_randomiser
from dsp.systems import ccsds_ldpc
from dsp.systems.catalogue import CATALOGUE
from dsp.systems.match import MATCH_ALPHA, Candidate, Findings, match

ENTRY = "ccsds-tm-ldpc"
SYSTEM_NAME = "CCSDS TM LDPC (AR4JA)"
R12 = "CCSDS TM k=1024 r1/2"
R23 = "CCSDS TM k=1024 r2/3"
R45 = "CCSDS TM k=1024 r4/5"
K4_R45 = "CCSDS TM k=4096 r4/5"
# The encoder's parity map for the two big k = 4096 codes takes 30 s and 7 minutes (galois).
SLOW = pytest.mark.slow
ALL_CODES = [
    R12,
    R23,
    R45,
    pytest.param("CCSDS TM k=4096 r1/2", marks=SLOW),
    pytest.param("CCSDS TM k=4096 r2/3", marks=SLOW),
    K4_R45,
]
NOISE_DB = -20.0
SPS = 8
FS = 48_000.0


def _llr(sent: Any, ec_n0_db: float | None, seed: int = 5) -> Any:
    """Soft bits for BPSK-like signalling at `ec_n0_db` (energy per transmitted bit over N0);
    None gives the noiseless +-1 stream. Positive means bit 0, as everywhere in dsp."""
    x = 1.0 - 2.0 * np.asarray(sent, np.float64)
    if ec_n0_db is None:
        return x
    sigma = math.sqrt(1.0 / (2.0 * 10 ** (ec_n0_db / 10)))
    y = x + np.random.default_rng(seed).normal(0.0, sigma, len(x))
    return 2.0 * y / sigma**2


def _stream(system: CcsdsLdpc, frames: int = 5) -> tuple[Any, Any]:
    period = ccsds_ldpc.period(ldpc.by_name(system.code))
    rows, _, sent = system.stream(frames * period, np.random.default_rng(1))
    return rows, sent


def _candidate(llr: Any, modulation: str = "QPSK") -> Candidate:
    return Candidate(modulation, Findings(modulation=modulation), None, llr=llr)


def _hex(rows: Any) -> list[str]:
    return [bytes(r).hex().upper() for r in rows]


def _ldpc_rows(result: Any) -> list[Any]:
    return [r for r in result.rows if r.candidate.startswith(SYSTEM_NAME)]


# --- the catalogue entry and the randomiser --------------------------------------------------


def test_the_randomiser_is_the_standards_sequence_and_two_implementations_agree() -> None:
    sequence = ccsds_randomiser(255 * 2)
    first = np.packbits(sequence[:64]).tobytes()
    assert first == bytes.fromhex("FF480EC09A0D70BC")  # as 131.0-B lists the sequence
    assert np.array_equal(sequence[:255], sequence[255:])  # period 255
    assert np.array_equal(sequence, CCSDS.sequence(510))  # the decoder side's LFSR agrees


def test_the_catalogue_names_the_six_codes_the_check_runs() -> None:
    entry = next(e for e in CATALOGUE.entries if e.id == ENTRY)
    assert entry.check == "ccsds-ldpc" and entry.name == SYSTEM_NAME
    assert set(entry.modulations) == {"BPSK", "QPSK"}
    assert set(entry.codes) == {c.name for c in ccsds_ldpc.CODES} and len(entry.codes) == 6
    assert CATALOGUE.version != "0.2.0"  # the catalogue changed, so its version moved
    assert {c.transmitted for c in ccsds_ldpc.CODES} == {2048, 1536, 1280, 8192, 6144, 5120}
    assert len({ccsds_ldpc.period(c) for c in ccsds_ldpc.CODES}) == 6  # each period names one code


def test_the_synth_stream_is_marker_then_randomised_codeword_and_the_message_is_systematic() -> (
    None
):
    system = CcsdsLdpc(R45)
    rows, sent = _stream(system, 3)
    code = ldpc.by_name(R45)
    period = ccsds_ldpc.period(code)
    marker = np.unpackbits(np.frombuffer(bytes.fromhex("1ACFFC1D"), np.uint8))
    assert np.array_equal(sent[:32], marker) and np.array_equal(sent[period : period + 32], marker)
    word = sent[32:period] ^ ccsds_randomiser(code.transmitted)  # not the marker: just the word
    assert np.array_equal(
        word[: code.k], np.unpackbits(rows[0])
    )  # the first k bits are the message
    assert word.shape == (code.transmitted,)


# --- exact decode of each code ---------------------------------------------------------------


@pytest.mark.parametrize("name", ALL_CODES)
@pytest.mark.parametrize("modulation", ["QPSK", "BPSK"])
def test_every_code_is_verified_by_its_own_check_and_the_messages_read_back_exactly(
    name: str, modulation: str
) -> None:
    rows, sent = _stream(CcsdsLdpc(name), 4)
    result = match([_candidate(_llr(sent, 6.0), modulation)], None, MATCH_ALPHA)
    assert result.verified is not None and result.verified.id == ENTRY
    assert result.proof is not None and result.proof.kind == "sync_recurrence"
    assert "syndrome 0" in result.proof.detail
    truth = _hex(rows)
    got = [f.payload_hex for f in result.frames if f.crc == "pass"]
    assert len(got) >= 3 and got == truth[: len(got)]  # the info bits, exactly
    assert all(f.sync_word == "0x1ACFFC1D" for f in result.frames)
    # The ledger shows every code tried: one row each, one accepted, the other five with p = 1.
    rows_ = _ldpc_rows(result)
    assert len(rows_) == 6
    accepted = [r for r in rows_ if r.outcome == "accepted"]
    assert len(accepted) == 1 and name.removeprefix("CCSDS TM ") in accepted[0].candidate
    assert accepted[0].p_value is not None and accepted[0].p_value < 1e-100
    assert all(r.p_value == 1.0 for r in rows_ if r.outcome == "rejected")
    assert result.tried >= 6
    system = next(p for p in result.stage.parameters if p.id == "system")
    assert system.level is EvidenceLevel.VERIFIED and system.value == SYSTEM_NAME
    code = next(p for p in result.stage.parameters if p.id == "ldpc_code")
    assert code.level is EvidenceLevel.VERIFIED and name in str(code.value)
    assert code.proof is not None and code.proof.kind == "sync_recurrence"


def test_the_evidence_carries_the_syndrome_the_distance_bound_and_the_p_value() -> None:
    _, sent = _stream(CcsdsLdpc(R12), 4)
    result = match([_candidate(_llr(sent, 4.0))], None, MATCH_ALPHA)
    system = next(p for p in result.stage.parameters if p.id == "system")
    text = " ".join(system.evidence)
    assert "0 of 1,536 parity checks unsatisfied" in text
    assert "Hamming distance" in text and "marker recurrence" in text
    assert "with the CCSDS pseudo-randomiser" in text or "randomiser" in text
    assert system.proof is not None and "2,080 bits" in system.proof.detail
    # the frames' header column is split at the primary header, shown as a HYPOTHESIS (no FECF)
    header = next(p for p in result.stage.parameters if p.id == "tm_header")
    assert header.level is EvidenceLevel.HYPOTHESIS and header.convention
    assert "spacecraft 0x1a5" in str(header.value) and "virtual channel 2" in str(header.value)
    first = next(f for f in result.frames if f.crc == "pass")
    assert len(first.header_hex.split(" ")) == 6


def test_the_check_works_from_hard_decisions_alone() -> None:
    rows, sent = _stream(CcsdsLdpc(R23), 4)
    cand = Candidate("BPSK", Findings(modulation="BPSK"), np.asarray(sent, np.uint8))
    result = match([cand], None, MATCH_ALPHA)
    assert result.verified is not None and result.verified.id == ENTRY
    assert [f.payload_hex for f in result.frames if f.crc == "pass"][:3] == _hex(rows)[:3]


@pytest.mark.parametrize("complement", [False, True])
@pytest.mark.parametrize(
    ("swap", "invert"), [(False, False), (False, True), (True, False), (True, True)]
)
def test_a_qpsk_carrier_rotation_or_mirror_and_a_complemented_stream_are_all_found(
    swap: bool, invert: bool, complement: bool
) -> None:
    """The ambiguity of the carrier phase reaches the bits as a swap of each pair and the
    inversion of one bit (a 90 degree rotation does both; 180 degrees inverts both); the check
    undoes each arrangement and the polarity itself."""
    rows, sent = _stream(CcsdsLdpc(R45), 4)
    pairs = np.asarray(sent, np.uint8)[: len(sent) // 2 * 2].reshape(-1, 2)
    bits = pairs[:, ::-1] if swap else pairs
    bits = bits ^ np.array([0, 1 if invert else 0], np.uint8)
    stream = bits.ravel() ^ (1 if complement else 0)
    result = match([_candidate(_llr(stream, 6.0), "QPSK")], None, MATCH_ALPHA)
    assert result.verified is not None and result.verified.id == ENTRY
    assert [f.payload_hex for f in result.frames if f.crc == "pass"][:3] == _hex(rows)[:3]


def test_a_burst_starting_mid_stream_and_a_noisy_low_snr_stream_are_still_found() -> None:
    rows, sent = _stream(CcsdsLdpc(R12), 6)
    cut = np.asarray(sent)[777:]  # starts inside a code word
    result = match([_candidate(_llr(cut, 2.0), "BPSK")], None, MATCH_ALPHA)
    assert result.verified is not None and result.verified.id == ENTRY
    got = [f.payload_hex for f in result.frames if f.crc == "pass"]
    assert len(got) >= 3 and got == _hex(rows)[1 : 1 + len(got)]


def test_one_flipped_bit_per_codeword_is_a_channel_error_and_is_corrected_and_shown() -> None:
    """A code word with one bit wrong is the standard's code word with a channel error, which an
    LDPC decoder corrects: it is verified, and the Hamming distance of 1 is in the evidence. (It
    cannot be told from noise, so it is not a near-miss; a wrong code word is.)"""
    rows, sent = _stream(CcsdsLdpc(R12, flips=1), 4)
    result = match([_candidate(_llr(sent, None))], None, MATCH_ALPHA)
    assert result.verified is not None and result.verified.id == ENTRY
    system = next(p for p in result.stage.parameters if p.id == "system")
    assert system.proof is not None and "Hamming distances 1, 1, 1" in system.proof.detail
    assert [f.payload_hex for f in result.frames if f.crc == "pass"][:3] == _hex(rows)[:3]


def test_a_stream_without_the_randomiser_verifies_and_says_it_is_not_the_standards() -> None:
    rows, sent = _stream(CcsdsLdpc(R45, randomiser="none"), 4)
    result = match([_candidate(_llr(sent, 6.0))], None, MATCH_ALPHA)
    assert result.verified is not None and result.verified.id == ENTRY
    system = next(p for p in result.stage.parameters if p.id == "system")
    assert "WITHOUT the CCSDS pseudo-randomiser" in " ".join(system.evidence)
    assert [f.payload_hex for f in result.frames if f.crc == "pass"][:3] == _hex(rows)[:3]


# --- near-misses and noise ---------------------------------------------------------------------


def _no_system(result: Any) -> None:
    assert result.verified is None
    system = next(p for p in result.stage.parameters if p.id == "system")
    assert system.level is EvidenceLevel.UNKNOWN and system.value is None
    assert system.evidence and system.resolve_hint
    assert not any(f.crc == "pass" for f in result.frames)
    rows = _ldpc_rows(result)
    assert len(rows) == 6 and all(r.outcome == "rejected" for r in rows)


@pytest.mark.parametrize(
    "system",
    [
        CcsdsLdpc(R12, randomiser="wrong"),
        CcsdsLdpc(R12, asm=False),
        CcsdsLdpc(R12, fault="shuffle"),
        CcsdsLdpc(R12, fault="parity"),
        CcsdsLdpc(R12, fault="other-code"),  # the r2/3 word padded to the r1/2 period
        CcsdsLdpc(R45, fault="other-code"),  # the r1/2 word cut to the r4/5 period
        CcsdsLdpc(R12, flips=300),  # 15 % of the bits wrong: beyond what the check claims
    ],
    ids=[
        "wrong-randomiser",
        "no-asm",
        "shuffled",
        "bad-parity",
        "r23-in-r12",
        "r12-in-r45",
        "15pct",
    ],
)
def test_near_misses_are_not_verified_and_the_unknown_system_says_why(system: CcsdsLdpc) -> None:
    _, sent = _stream(system, 5)
    result = match([_candidate(_llr(sent, None))], None, MATCH_ALPHA)
    _no_system(result)
    text = " ".join(next(p for p in result.stage.parameters if p.id == "system").evidence)
    assert "CCSDS TM LDPC (AR4JA)" in text and "k=1024" in text


def test_the_asm_with_a_recurring_period_but_random_codewords_is_not_verified() -> None:
    """The marker recurs at the code's period, so the decoder runs on every candidate; it must
    find no code word in random bodies, and none in an all-zero body (a degenerate code word)."""
    rng = np.random.default_rng(9)
    marker = np.unpackbits(np.frombuffer(bytes.fromhex("1ACFFC1D"), np.uint8))
    for body in ("random", "zeros"):
        for code in (R12, R45):
            n = ldpc.by_name(code).transmitted
            blocks = [
                np.concatenate(
                    [
                        marker,
                        rng.integers(0, 2, n, np.uint8)
                        if body == "random"
                        else np.zeros(n, np.uint8),
                    ]
                )
                for _ in range(6)
            ]
            result = match([_candidate(_llr(np.concatenate(blocks), None))], None, MATCH_ALPHA)
            _no_system(result)
            running = [r for r in ccsds_ldpc.scan(_llr(np.concatenate(blocks), None), "QPSK").runs]
            assert any(r.pairs > 0 for r in running)  # the recurrence was seen and then refused
            assert not any(r.verified for r in running)


def test_a_wrong_code_at_the_right_period_is_rejected_with_the_reason_in_the_ledger() -> None:
    _, sent = _stream(CcsdsLdpc(R12, fault="shuffle"), 5)
    result = match([_candidate(_llr(sent, None))], None, MATCH_ALPHA)
    row = next(r for r in _ldpc_rows(result) if "k=1024 r1/2" in r.candidate)
    assert "recurs" in row.reason and "decode to a CCSDS TM k=1024 r1/2 code word" in row.reason
    assert row.outcome == "rejected" and row.p_value == 1.0


def test_streams_too_short_for_two_markers_are_not_checked_and_are_not_a_consistent_with() -> None:
    result = match([_candidate(np.ones(1000))], None, MATCH_ALPHA)
    assert result.verified is None
    system = next(p for p in result.stage.parameters if p.id == "system")
    assert system.level is EvidenceLevel.UNKNOWN  # not "consistent with ...; check could not run"
    assert "Too few bits" in " ".join(system.evidence) or "needs two markers" in " ".join(
        system.evidence
    )


@pytest.mark.parametrize("modulation", ["8PSK", "2FSK", "16QAM"])
def test_a_modulation_the_system_does_not_use_conflicts_and_runs_no_check(
    modulation: str,
) -> None:
    _, sent = _stream(CcsdsLdpc(R45), 4)
    result = match([_candidate(_llr(sent, None), modulation)], None, MATCH_ALPHA)
    assert result.verified is None
    assert not any(r.layer == "Match" and r.p_value is not None for r in _ldpc_rows(result))
    assert "Parameters conflict" in " ".join(r.statistic for r in _ldpc_rows(result))


def test_noise_uncoded_and_shuffled_streams_never_verify_over_hundreds_of_streams() -> None:
    """The check's false-accept rate on streams with no LDPC code word in them: 600 streams of
    Gaussian noise, random hard bits and a valid stream with its bits shuffled, as BPSK and QPSK
    and with each polarity, at lengths the chain hands over."""
    rng = np.random.default_rng(2026)
    _, valid = _stream(CcsdsLdpc(R45), 8)
    accepts = recurrences = 0
    for i in range(600):
        kind = i % 3
        n = int(rng.integers(8_000, 40_000))
        if kind == 0:
            x = rng.normal(size=n) * rng.uniform(0.5, 5.0)
        elif kind == 1:
            x = 1.0 - 2.0 * rng.integers(0, 2, n)
        else:
            x = _llr(rng.permutation(np.asarray(valid)), 6.0, seed=i)
        scan = ccsds_ldpc.scan(x, "QPSK" if i % 2 else "BPSK")
        accepts += scan.best is not None
        recurrences += sum(r.pairs > 0 for r in scan.runs)
    assert accepts == 0
    assert recurrences == 0  # not even a chance marker pair in 600 random streams


def test_the_p_value_is_the_product_of_the_marker_recurrence_and_the_distance_bounds() -> None:
    _, sent = _stream(CcsdsLdpc(R12), 5)
    scan = ccsds_ldpc.scan(_llr(sent, 4.0), "BPSK")
    run = scan.best
    assert run is not None and run.verified and run.valid == run.scanned == 6
    assert run.hypotheses == 4  # one arrangement x 2 polarities x randomiser on or off
    blocks = [b for b in run.blocks if b.valid][: run.valid]
    expected = (
        run.log10_p_asm
        + sum(b.log2_p for b in blocks) * math.log10(2)
        + math.log10(math.comb(run.scanned, run.valid))
        + math.log10(run.hypotheses)
    )
    assert run.log10_p == pytest.approx(expected, abs=1e-6)
    # The marker recurrence alone: a random position matches within 3 errors with probability
    # 5489 / 2^32 (1 + 32 + 496 + 4960), and a chain of pairs is that squared per pair.
    hit = (1 + 32 + 496 + 4960) / 2.0**32
    pairs = run.pairs
    lam = (len(sent) - run.period - 32) * hit**2
    assert run.log10_p_asm == pytest.approx(
        math.log10(
            sum(math.exp(-lam) * lam**j / math.factorial(j) for j in range(pairs, pairs + 20))
        ),
        rel=1e-6,
    )
    # One block: 2^1024 x P(Binomial(2048, 1/2) <= d), recomputed exactly with integers.
    block = blocks[0]
    tail = sum(math.comb(2048, i) for i in range(block.distance + 1))
    exact = (1024 + math.log2(tail) - 2048) if tail else -2048
    assert block.log2_p == pytest.approx(min(0.0, exact), abs=1e-6)
    assert block.log2_p < -400  # at 4 dB per bit (about 1.3 % raw errors)


def test_the_check_costs_milliseconds_on_noise() -> None:
    """Every demodulated PSK branch pays this: 100,000 soft bits, QPSK (four arrangements)."""
    import time

    x = np.random.default_rng(1).normal(size=100_000)
    ccsds_ldpc.scan(x, "QPSK")  # compile and warm
    start = time.perf_counter()
    for _ in range(5):
        ccsds_ldpc.scan(x, "QPSK")
    assert (time.perf_counter() - start) / 5 < 0.25


# --- end to end through detect and analyse -----------------------------------------------------


class Memory:
    def __init__(self, x: Any) -> None:
        self.x = np.asarray(x)
        self.num_samples = len(self.x)

    def read(self, start: int, count: int) -> Any:
        return self.x[start : start + count]


def _recording(
    system: CcsdsLdpc, modulation: str = "qpsk", frames: float = 3.5, esn0: float = 15.0
) -> tuple[Any, DetectionReport]:
    period = ccsds_ldpc.period(ldpc.by_name(system.code))
    bits_per_symbol = 2 if modulation == "qpsk" else 1
    duration = int(frames * period / bits_per_symbol * SPS) + 4000
    samples = 1 << (duration + 8000 - 1).bit_length()
    power = NOISE_DB + esn0 - 10 * math.log10(SPS)
    spec = SignalSpec(
        modulation=modulation,
        sps=SPS,
        power_db=power,
        start=2000,
        duration=duration,
        frame=None,
        system=system,
    )
    g = generate(Scene(samples=samples, signals=(spec,), noise_db=NOISE_DB, sample_rate=FS), 7)
    source = Memory(g.samples)
    detections = detect(source, real=False).detections
    assert detections
    main = max(detections, key=lambda d: (d.stop - d.start) * (d.high - d.low))
    return g, analyse(source, main, sample_rate=FS)


def _match_stage(report: DetectionReport) -> Any:
    return next(s for s in report.stages if s.id == "match")


def _check_recording(name: str, modulation: str) -> None:
    g, report = _recording(CcsdsLdpc(name), modulation)
    assert report.level is EvidenceLevel.VERIFIED
    stage = _match_stage(report)
    system = next(p for p in stage.parameters if p.id == "system")
    assert system.level is EvidenceLevel.VERIFIED and system.value == SYSTEM_NAME
    assert system.proof is not None and system.proof.kind == "sync_recurrence"
    code = next(p for p in stage.parameters if p.id == "ldpc_code")
    assert name in str(code.value)
    truth = _hex(g.signals[0].payloads)
    passing = [f for f in report.frames if f.crc == "pass"]
    assert len(passing) >= 2
    first = truth.index(passing[0].payload_hex)  # the first marker may be lost at the burst's edge
    assert [f.payload_hex for f in passing] == truth[first : first + len(passing)]
    assert "CCSDS TM LDPC (AR4JA)" in report.headline
    assert report.search is not None and report.search.match_tried >= 6
    rows = [r for r in report.search.rows if r.layer == "Match" and "CCSDS TM LDPC" in r.candidate]
    assert len(rows) == 6 and sum(r.outcome == "accepted" for r in rows) == 1
    # The blind stages stand as the chain found them: no catalogued code or CRC fit.
    assert next(s for s in report.stages if s.id == "fec").level is EvidenceLevel.UNKNOWN


@pytest.mark.parametrize("name", [R12, R23, R45, K4_R45])
def test_a_qpsk_recording_is_verified_and_its_info_bits_read_back_through_analyse(
    name: str,
) -> None:
    _check_recording(name, "qpsk")


def test_a_bpsk_recording_is_verified_through_analyse() -> None:
    _check_recording(R45, "bpsk")


@pytest.mark.parametrize("name", ["CCSDS TM k=4096 r1/2", "CCSDS TM k=4096 r2/3"])
@SLOW
def test_the_two_large_codes_are_verified_through_analyse(name: str) -> None:
    _check_recording(name, "qpsk")


def test_a_near_miss_recording_is_not_verified_through_analyse_and_the_level_stays_down() -> None:
    """Right marker and period, wrong randomiser: Match finds no system, the blind chain finds
    no CRC, and nothing raises the level."""
    _, report = _recording(CcsdsLdpc(R45, randomiser="wrong"), "qpsk", frames=3.0)
    system = next(p for p in _match_stage(report).parameters if p.id == "system")
    assert system.level is EvidenceLevel.UNKNOWN and system.value is None
    assert report.level is not EvidenceLevel.VERIFIED and not report.frames
    assert report.search is not None
    assert not any(r.outcome == "accepted" for r in report.search.rows)
    rows = [r for r in report.search.rows if r.layer == "Match" and "CCSDS TM LDPC" in r.candidate]
    assert len(rows) == 6
