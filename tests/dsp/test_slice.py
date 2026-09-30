"""The decode chain end to end: a dsp.synth recording through detect and analyse, checked
against the exact transmitted frames (PLAN M3-M6)."""

import math
from dataclasses import replace
from typing import Any

import numpy as np
import pytest

from dsp.analyse import analyse
from dsp.detect import Detection, detect
from dsp.evidence import EvidenceLevel
from dsp.fec.viterbi import decode, encode
from dsp.report import DetectionReport
from dsp.synth import fec
from dsp.synth import interleave as il
from dsp.synth.bits import FrameSpec, to_bytes
from dsp.synth.chain import Generated, Scene, SignalSpec, generate

NOISE_DB = -20.0


class Memory:
    def __init__(self, x: Any) -> None:
        self.x = np.asarray(x)
        self.num_samples = len(self.x)

    def read(self, start: int, count: int) -> Any:
        return self.x[start : start + count]


def _spec(modulation: str, sps: int, esn0_db: float, **kw: Any) -> SignalSpec:
    power = NOISE_DB + esn0_db - 10 * math.log10(sps)
    return SignalSpec(modulation=modulation, sps=sps, power_db=power, **kw)


def _run(
    spec: SignalSpec, seed: int = 7, mirror: bool = False
) -> tuple[Generated, DetectionReport]:
    """`mirror` conjugates the recording: I and Q swapped, so the spectrum is mirrored."""
    g = generate(Scene(samples=1 << 18, signals=(spec,), noise_db=NOISE_DB), seed)
    source = Memory(np.conj(g.samples) if mirror else g.samples)
    detections = detect(source, real=False).detections
    assert detections, "the signal must be detected"
    main = max(detections, key=lambda d: (d.stop - d.start) * (d.high - d.low))
    return g, analyse(source, main)


def _truth_bodies(g: Generated) -> list[str]:
    """Hex of each transmitted frame between its sync word and its CRC."""
    spec = FrameSpec()
    rows = g.signals[0].framed.reshape(-1, spec.length)
    return [to_bytes(r[len(spec.sync_bits) : -16]).hex().upper() for r in rows]


CONV = fec.Convolutional(7, fec.K7)


@pytest.mark.parametrize(
    ("modulation", "sps", "offset", "esn0"),
    [
        ("qpsk", 8, 37, 15.0),
        ("bpsk", 16, 0, 15.0),
        ("8psk", 8, 3, 15.0),
        ("16qam", 8, 11, 15.0),
        ("64qam", 8, 11, 25.0),  # 64QAM needs the SNR its 6 bits per symbol ask for
    ],
)
def test_coded_psk_decodes_to_the_transmitted_frames(
    modulation: str, sps: int, offset: int, esn0: float
) -> None:
    spec = _spec(modulation, sps, esn0, inner=CONV, stream_offset=offset, offset=0.1)
    spec = replace(spec, start=10_000, duration=200_000)
    g, report = _run(spec)
    assert report.level is EvidenceLevel.VERIFIED
    assert report.label == modulation.upper()
    truth = _truth_bodies(g)
    passing = [f for f in report.frames if f.crc == "pass"]
    # Every complete frame in the burst decodes; allow the first to be lost to decoder start-up.
    frame_bits = 2 * FrameSpec().length
    symbols = 200_000 / sps
    expected = (
        int(
            symbols
            * {"qpsk": 2, "bpsk": 1, "8psk": 3, "16qam": 4, "64qam": 6}[modulation]
            / frame_bits
        )
        - 2
    )
    assert len(passing) >= expected
    for f in passing:
        assert f.payload_hex in truth
    indices = [truth.index(f.payload_hex) for f in passing]
    assert indices == list(range(indices[0], indices[0] + len(indices)))
    classify = next(s for s in report.stages if s.id == "classify")
    assert classify.parameters[0].value == modulation.upper()
    assert classify.parameters[0].level is EvidenceLevel.VERIFIED
    assert report.search is not None
    assert report.search.shuffled_runs > 0 and report.search.shuffled_accepts == 0
    assert sum(r.outcome == "accepted" for r in report.search.rows) == 1


def test_a_chain_that_also_passes_on_shuffled_bits_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shuffled-bit control gates acceptance: a decode that would be VERIFIED is not, when
    shuffling its bits still gets past the threshold, and the ledger says that is why."""
    monkeypatch.setattr("dsp.analyse._shuffled_accepts", lambda chain, threshold: 1)
    spec = replace(_spec("qpsk", 8, 15.0, inner=CONV, stream_offset=5, offset=0.1), start=10_000)
    _, report = _run(replace(spec, duration=100_000))
    assert report.level is not EvidenceLevel.VERIFIED
    assert report.search is not None
    assert report.search.shuffled_accepts >= 1 and report.search.shuffled_runs > 0
    assert report.search.shuffled_blocked >= 1
    assert not any(r.outcome == "accepted" for r in report.search.rows)
    blocked = [r for r in report.search.rows if r.reason.startswith("Blocked")]
    assert blocked and all("shuffled" in r.reason for r in blocked)


def test_a_blocked_chain_hands_acceptance_to_the_next_one_that_passes_the_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def first_fails(chain: Any, threshold: float) -> int:
        calls.append(1)
        return 1 if len(calls) == 1 else 0

    monkeypatch.setattr("dsp.analyse._shuffled_accepts", first_fails)
    spec = replace(_spec("qpsk", 8, 15.0, inner=CONV, stream_offset=5, offset=0.1), start=10_000)
    _, report = _run(replace(spec, duration=100_000))
    assert report.search is not None
    assert len(calls) >= 2, "the decode should be significant under more than one description"
    assert report.search.shuffled_blocked == 1
    assert report.search.shuffled_accepts == 1  # the blocked chain's run, none for the accepted one
    assert report.search.shuffled_runs == 3 * len(calls)
    assert sum(r.outcome == "accepted" for r in report.search.rows) == 1
    assert report.level is EvidenceLevel.VERIFIED


@pytest.mark.parametrize(
    ("modulation", "sps", "esn0", "mirror"),
    [
        ("2fsk", 8, 15.0, False),
        ("4fsk", 8, 15.0, False),
        ("8fsk", 16, 22.0, False),  # 8 tones h = 1 apart span 7 symbol rates: room to breathe
        ("4fsk", 8, 15.0, True),  # a swapped I/Q flips only each label's first bit
        ("8fsk", 16, 22.0, True),
    ],
    ids=["2fsk", "4fsk", "8fsk", "4fsk-mirrored", "8fsk-mirrored"],
)
def test_coded_fsk_decodes_to_the_transmitted_frames(
    modulation: str, sps: int, esn0: float, mirror: bool
) -> None:
    order = int(modulation[0])
    name = modulation.upper()
    spec = _spec(modulation, sps, esn0, inner=CONV, stream_offset=5, offset=0.1)
    g, report = _run(spec, mirror=mirror)
    assert report.kind == "fsk" and report.label == name
    assert report.level is EvidenceLevel.VERIFIED
    truth = _truth_bodies(g)
    passing = [f for f in report.frames if f.crc == "pass"]
    bits = (1 << 18) / sps * math.log2(order)
    assert len(passing) >= int(bits / (2 * FrameSpec().length)) - 3
    assert all(f.payload_hex in truth for f in passing)
    indices = [truth.index(f.payload_hex) for f in passing]
    assert indices == list(range(indices[0], indices[0] + len(indices)))
    classify = next(s for s in report.stages if s.id == "classify")
    assert classify.parameters[0].value == name
    assert classify.parameters[0].level is EvidenceLevel.VERIFIED
    assert report.search is not None and report.search.shuffled_accepts == 0
    accepted = next(r for r in report.search.rows if r.outcome == "accepted")
    # Only a spectrum mirrored across more than two tones needs the mirrored branch: for two
    # tones it inverts every bit, which the sync search's inverted-sync check reads itself.
    assert ("mirrored" in accepted.candidate) == (mirror and order > 2)


def test_block_interleaved_frames_decode_with_the_interleaver_found() -> None:
    spec = _spec(
        "qpsk", 8, 15.0, inner=CONV, interleaver=il.Block(16, 36), stream_offset=301, offset=0.1
    )
    g, report = _run(spec)
    assert report.level is EvidenceLevel.VERIFIED
    truth = _truth_bodies(g)
    passing = [f for f in report.frames if f.crc == "pass"]
    assert len(passing) >= 50
    indices = [truth.index(f.payload_hex) for f in passing]
    assert indices == list(range(indices[0], indices[0] + len(indices)))
    assert report.search is not None
    accepted = next(r for r in report.search.rows if r.outcome == "accepted")
    assert accepted.layer == "Interleaver" and "block 16x36" in accepted.candidate
    assert report.search.shuffled_accepts == 0


def test_rs_concatenated_frames_all_decode_through_the_outer_code() -> None:
    spec = _spec("qpsk", 8, 15.0, inner=CONV, outer=fec.RS_CCSDS, stream_offset=77, offset=0.1)
    g, report = _run(spec)
    assert report.level is EvidenceLevel.VERIFIED
    truth = _truth_bodies(g)
    passing = [f for f in report.frames if f.crc == "pass"]
    # Without the outer code, frames straddling the parity bytes fail; through it, all pass.
    assert len(passing) >= 44 and len(passing) >= len(report.frames) - 2
    indices = [truth.index(f.payload_hex) for f in passing]
    assert indices == list(range(indices[0], indices[0] + len(indices)))
    fec_stage = next(s for s in report.stages if s.id == "fec")
    outer = next(p for p in fec_stage.parameters if p.id == "outer_code")
    assert outer.value == "RS(255,223) CCSDS" and outer.level is EvidenceLevel.VERIFIED
    assert report.search is not None and report.search.shuffled_accepts == 0


def test_uncoded_random_data_is_not_verified() -> None:
    _, report = _run(_spec("qpsk", 16, 15.0, frame=None, offset=-0.1))
    assert report.level is not EvidenceLevel.VERIFIED
    assert not report.frames and report.no_frames_reason
    fec_stage = next(s for s in report.stages if s.id == "fec")
    assert fec_stage.parameters[0].level is EvidenceLevel.UNKNOWN


def test_repetition_coded_frames_are_decoded_as_the_equivalent_convolutional_code() -> None:
    """A repetition-3 code is a degenerate rate-1/3 convolutional code (K = 1), which the blind
    search names by an equivalent K = 2 description. It is not identified as "repetition" (the
    catalogue has no such entry yet), but it decodes, and the CRC proves it."""
    g, report = _run(_spec("qpsk", 8, 15.0, inner=fec.Repetition(3), offset=0.05))
    assert report.level is EvidenceLevel.VERIFIED
    truth = _truth_bodies(g)
    passing = [f for f in report.frames if f.crc == "pass"]
    assert len(passing) >= 30 and all(f.payload_hex in truth for f in passing)
    fec_stage = next(s for s in report.stages if s.id == "fec")
    code = next(p for p in fec_stage.parameters if p.id == "code")
    assert "r1/3" in str(code.value) and code.level is EvidenceLevel.VERIFIED
    assert report.search is not None and report.search.shuffled_accepts == 0


def test_noise_gives_no_verified_result() -> None:
    rng = np.random.default_rng(3)
    x = (rng.normal(size=1 << 17) + 1j * rng.normal(size=1 << 17)) * 0.07
    box = Detection(0, 1 << 17, 0.05, 0.2, nfft=1024, snr_db=0.0, score=0.0, cells=0)
    report = analyse(Memory(x), box)
    assert report.level is not EvidenceLevel.VERIFIED
    assert not any(f.crc == "pass" for f in report.frames)


def test_analog_fm_skips_the_digital_chain() -> None:
    spec = SignalSpec(modulation="fm", power_db=NOISE_DB + 30, offset=0.2, fm_deviation=0.05)
    _, report = _run(spec)
    assert report.kind == "analog"
    assert report.search is None and report.no_search_reason


def test_viterbi_inverts_the_synth_encoder() -> None:
    rng = np.random.default_rng(1)
    u = rng.integers(0, 2, 5000, dtype=np.uint8)
    coded = CONV.encode(u)
    assert np.array_equal(encode(u), coded)
    llr = 1.0 - 2.0 * coded.astype(np.float64) + rng.normal(0, 0.5, len(coded))
    assert np.array_equal(decode(llr), u)


@pytest.mark.parametrize(
    ("constraint", "generators", "modulation", "offset", "polarity_read"),
    [
        (9, (0o561, 0o753), "qpsk", 37, False),  # not in the catalogue; even-weight checks
        (7, (0o133, 0o171, 0o165), "qpsk", 5, False),  # rate 1/3
        (3, (0o7, 0o5), "bpsk", 1, True),  # odd-weight checks: the stream's polarity is read
    ],
)
def test_a_code_outside_the_catalogue_is_found_blind_and_decodes_to_the_transmitted_frames(
    constraint: int, generators: tuple[int, ...], modulation: str, offset: int, polarity_read: bool
) -> None:
    code = fec.Convolutional(constraint, generators)
    spec = _spec(modulation, 8, 15.0, inner=code, stream_offset=offset, offset=0.1)
    spec = replace(spec, start=10_000, duration=200_000)
    g, report = _run(spec)
    assert report.level is EvidenceLevel.VERIFIED
    truth = _truth_bodies(g)
    passing = [f for f in report.frames if f.crc == "pass"]
    assert len(passing) >= 20
    for f in passing:
        assert f.payload_hex in truth
    indices = [truth.index(f.payload_hex) for f in passing]
    assert indices == list(range(indices[0], indices[0] + len(indices)))

    assert report.search is not None and report.search.shuffled_accepts == 0
    accepted = next(r for r in report.search.rows if r.outcome == "accepted")
    assert accepted.layer == "FEC" and "blind search" in accepted.candidate
    fec_stage = next(s for s in report.stages if s.id == "fec")
    found = next(p for p in fec_stage.parameters if p.id == "code")
    assert found.level is EvidenceLevel.VERIFIED  # by the CRC, not by the search itself
    assert f"K={constraint} r1/{len(generators)}" in str(found.value)
    assert ",".join(f"{gen:o}" for gen in generators) in str(found.value)
    # Honest about what was found: an equivalent description, blind, with its own accounting.
    assert any("equivalent description" in w for w in found.warnings)
    assert any("no catalogue entry to start from" in e for e in found.evidence)
    assert any("hypotheses)" in e for e in found.evidence)
    assert "(found blind)" in report.headline
    assert "(found blind)" in fec_stage.summary
    assert report.search.blind_searched >= 1 and report.search.blind_identified >= 1
    alignment = next(p for p in fec_stage.parameters if p.id == "code_alignment")
    polarity = next(p for p in fec_stage.parameters if p.id == "stream_polarity")
    assert alignment.level is polarity.level is EvidenceLevel.VERIFIED
    assert polarity.value in ("upright", "inverted")
    assert any("even weight" in e for e in polarity.evidence) is not polarity_read


@pytest.mark.parametrize(("rate", "offset"), [("2/3", 0), ("3/4", 7), ("5/6", 13), ("7/8", 31)])
def test_a_punctured_code_is_decoded_at_its_rate_and_phase(rate: str, offset: int) -> None:
    """DVB-S puncturing of the K=7 code, the stream starting `offset` sent bits in: the search
    finds the rate and the phase, and the CRC proves the frames."""
    spec = _spec(
        "qpsk",
        8,
        15.0,
        inner=fec.Convolutional(7, fec.K7, fec.PUNCTURES[rate]),
        stream_offset=offset,
        offset=0.1,
    )
    spec = replace(spec, start=10_000, duration=200_000)
    g, report = _run(spec)
    assert report.level is EvidenceLevel.VERIFIED
    truth = _truth_bodies(g)
    passing = [f for f in report.frames if f.crc == "pass"]
    assert len(passing) >= 20 and all(f.payload_hex in truth for f in passing)
    fec_stage = next(s for s in report.stages if s.id == "fec")
    code = next(p for p in fec_stage.parameters if p.id == "code")
    assert f"r{rate} punctured" in str(code.value)
    assert report.search is not None and report.search.shuffled_accepts == 0
    accepted = next(r for r in report.search.rows if r.outcome == "accepted")
    assert accepted.layer == "FEC" and f"r{rate} punctured" in accepted.candidate


def test_a_coded_but_unframed_stream_is_identified_yet_not_accepted() -> None:
    """The wiring's null case: a K=9 code (outside the catalogue) carrying no frame. The blind
    search may name the code, but nothing frames, so nothing is accepted or VERIFIED, and the
    report says how far the search got and what it covers."""
    spec = _spec("qpsk", 8, 15.0, frame=None, inner=fec.Convolutional(9, (0o561, 0o753)))
    _, report = _run(replace(spec, start=10_000, duration=200_000))
    assert report.level is not EvidenceLevel.VERIFIED and not report.frames
    assert report.search is not None
    assert not any(r.outcome == "accepted" for r in report.search.rows)
    assert report.search.blind_searched >= 1 and report.search.blind_identified >= 1
    assert report.search.shuffled_accepts == 0
    fec_stage = next(s for s in report.stages if s.id == "fec")
    reason = " ".join(fec_stage.parameters[0].evidence)
    assert "blind convolutional search covers non-recursive, unpunctured rate-1/n" in reason
    assert f"named a code on {report.search.blind_identified}" in reason


@pytest.mark.parametrize(
    ("interleaver", "label", "offset"),
    [
        (il.Helical(16, 36), "helical 16x36", 301),
        (il.Wifi(96, 2), "802.11 N_CBPS 96", 45),
        (il.Qpp(40, 3, 10), "LTE QPP K=40", 21),
        (il.Qpp(6144, 263, 480), "LTE QPP K=6144", 1001),
    ],
    ids=["helical", "802.11", "qpp-40", "qpp-6144"],
)
def test_helical_and_80211_interleavers_are_found_and_decoded(
    interleaver: il.BlockInterleaver, label: str, offset: int
) -> None:
    spec = _spec("qpsk", 8, 15.0, inner=CONV, interleaver=interleaver, stream_offset=offset)
    g, report = _run(replace(spec, offset=0.1))
    assert report.level is EvidenceLevel.VERIFIED
    truth = _truth_bodies(g)
    passing = [f for f in report.frames if f.crc == "pass"]
    assert len(passing) >= 40 and all(f.payload_hex in truth for f in passing)
    assert report.search is not None and report.search.shuffled_accepts == 0
    accepted = next(r for r in report.search.rows if r.outcome == "accepted")
    assert accepted.layer == "Interleaver" and label in accepted.candidate
    stage = next(s for s in report.stages if s.id == "deinterleave")
    assert stage.parameters[0].level is EvidenceLevel.VERIFIED and label in str(
        stage.parameters[0].value
    )


@pytest.mark.parametrize(
    ("branches", "step", "offset"), [(4, 3, 0), (5, 2, 7), (8, 1, 301)], ids=str
)
def test_convolutional_interleavers_are_found_at_their_lane_phase_and_decoded(
    branches: int, step: int, offset: int
) -> None:
    spec = _spec(
        "qpsk",
        8,
        15.0,
        inner=CONV,
        interleaver=il.Convolutional(branches, step),
        stream_offset=offset,
    )
    g, report = _run(replace(spec, offset=0.1))
    assert report.level is EvidenceLevel.VERIFIED
    truth = _truth_bodies(g)
    passing = [f for f in report.frames if f.crc == "pass"]
    # The delay lines' start-up lag costs the first frames, no more.
    assert len(passing) >= 40 and all(f.payload_hex in truth for f in passing)
    assert report.search is not None and report.search.shuffled_accepts == 0
    accepted = next(r for r in report.search.rows if r.outcome == "accepted")
    assert accepted.layer == "Interleaver"
    assert f"convolutional I={branches} M={step}" in accepted.candidate


def _truth_for(g: Generated, spec: FrameSpec) -> list[str]:
    """Hex of each transmitted frame between its sync word and its CRC field."""
    crc = fec_crc_width(spec)
    rows = g.signals[0].framed.reshape(-1, spec.length)
    return [to_bytes(r[len(spec.sync_bits) : -crc]).hex().upper() for r in rows]


def fec_crc_width(spec: FrameSpec) -> int:
    from dsp.synth.bits import CRCS

    return CRCS[spec.crc].width if spec.crc else 0


@pytest.mark.parametrize(
    ("frame", "inner", "offset", "named"),
    [
        # A CRC the catalogue has never heard of, straight off the modem.
        (FrameSpec(sync="POCSAG", crc="CRC-32/Q", payload_bytes=32), None, 0, False),
        # Behind the K=7 code, at an arbitrary bit alignment, with a shorter Barker sync.
        (FrameSpec(sync="Barker-13", crc="CRC-16/XMODEM", payload_bytes=24), CONV, 5, True),
    ],
    ids=["pocsag+crc32q", "conv+barker13"],
)
def test_frames_with_an_unknown_sync_word_and_crc_are_found_blind(
    frame: FrameSpec, inner: fec.Convolutional | None, offset: int, named: bool
) -> None:
    spec = _spec("qpsk", 8, 15.0, frame=frame, inner=inner, stream_offset=offset, offset=0.1)
    g, report = _run(replace(spec, start=10_000, duration=200_000))
    assert report.level is EvidenceLevel.VERIFIED
    truth = _truth_for(g, frame)
    passing = [f for f in report.frames if f.crc == "pass"]
    assert len(passing) >= 60
    # The table splits at the real header: the 16-bit counter the generator wrote, then the payload.
    assert all(len(f.header_hex.split()) == frame.counter_bits // 8 for f in passing)
    assert all(len(f.payload_hex) == 2 * frame.payload_bytes for f in passing)
    whole = [f.header_hex.replace(" ", "") + f.payload_hex for f in passing]
    if named:
        assert all(h in truth for h in whole)
    else:
        # An unnamed CRC can't fix the stream's polarity: the payload is what was sent or its
        # complement, and the report says so (below).
        complemented = {bytes(b ^ 0xFF for b in bytes.fromhex(h)).hex().upper() for h in truth}
        assert all(h in truth or h in complemented for h in whole)

    assert report.search is not None and report.search.shuffled_accepts == 0
    accepted = next(r for r in report.search.rows if r.outcome == "accepted")
    assert "blind framing" in accepted.candidate and "held-out" in accepted.statistic
    stage = next(s for s in report.stages if s.id == "frame")
    by_id = {p.id: p for p in stage.parameters}
    assert {"sync_word", "frame_length", "crc", "header"} <= set(by_id)
    assert by_id["frame_length"].value == frame.length
    if named:
        assert by_id["crc"].value == frame.crc  # the fit matches a catalogued name
    else:
        assert by_id["crc"].value == "CRC-32 poly 0x814141AB"
        assert any("complemented" in w for w in by_id["sync_word"].warnings)
    assert by_id["sync_word"].level is EvidenceLevel.VERIFIED
    assert any("constant prefix" in w for w in by_id["sync_word"].warnings)
    counter = "counter 16 (+1)" if named else "counter 16 (+65535)"  # complemented: counts down
    assert counter in str(by_id["header"].value)
    assert by_id["header"].level is EvidenceLevel.HYPOTHESIS  # judged on its own, not by the CRC
    assert any("held-out frames pass" in e for e in by_id["crc"].evidence)


@pytest.mark.parametrize("scrambler", ["CCSDS", "G3RUH"])
def test_scrambled_frames_are_found_through_the_descrambler_catalogue(scrambler: str) -> None:
    frame = FrameSpec()
    spec = _spec("qpsk", 8, 15.0, frame=frame, offset=0.1)
    spec = replace(spec, scrambler=scrambler, start=10_000, duration=200_000)
    g, report = _run(spec)
    assert report.level is EvidenceLevel.VERIFIED
    truth = _truth_bodies(g)
    passing = [f for f in report.frames if f.crc == "pass"]
    assert len(passing) >= 60 and all(f.payload_hex in truth for f in passing)
    stage = next(s for s in report.stages if s.id == "frame")
    d = next(p for p in stage.parameters if p.id == "descrambler")
    assert scrambler in str(d.value)
    assert d.level is EvidenceLevel.VERIFIED
    assert report.search is not None and report.search.shuffled_accepts == 0
    accepted = next(r for r in report.search.rows if r.outcome == "accepted")
    assert str(d.value) in accepted.candidate


@pytest.mark.parametrize(
    ("rows", "cols", "offset"), [(10, 30, 7), (20, 40, 301), (37, 19, 0)], ids=str
)
def test_a_block_interleaver_outside_the_catalogue_is_found_blind_and_decoded(
    rows: int, cols: int, offset: int
) -> None:
    spec = _spec(
        "qpsk",
        8,
        15.0,
        inner=CONV,
        interleaver=il.Block(rows, cols),
        stream_offset=offset,
        offset=0.1,
    )
    g, report = _run(spec)
    assert report.level is EvidenceLevel.VERIFIED
    truth = _truth_bodies(g)
    passing = [f for f in report.frames if f.crc == "pass"]
    assert len(passing) >= 40 and all(f.payload_hex in truth for f in passing)
    assert report.search is not None and report.search.shuffled_accepts == 0
    accepted = next(r for r in report.search.rows if r.outcome == "accepted")
    assert accepted.layer == "Interleaver"
    assert f"block {rows}x{cols} (found blind)" in accepted.candidate
    stage = next(s for s in report.stages if s.id == "deinterleave")
    assert stage.parameters[0].level is EvidenceLevel.VERIFIED
    assert "stride scan" in stage.parameters[0].method
    assert f"Every {rows}th received bit" in " ".join(stage.parameters[0].evidence)
