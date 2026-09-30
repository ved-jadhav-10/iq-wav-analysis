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


def _run(spec: SignalSpec, seed: int = 7) -> tuple[Generated, DetectionReport]:
    g = generate(Scene(samples=1 << 18, signals=(spec,), noise_db=NOISE_DB), seed)
    source = Memory(g.samples)
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
    ("modulation", "sps", "offset"),
    [("qpsk", 8, 37), ("bpsk", 16, 0), ("8psk", 8, 3), ("16qam", 8, 11)],
)
def test_coded_psk_decodes_to_the_transmitted_frames(
    modulation: str, sps: int, offset: int
) -> None:
    spec = _spec(modulation, sps, 15.0, inner=CONV, stream_offset=offset, offset=0.1)
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
        int(symbols * {"qpsk": 2, "bpsk": 1, "8psk": 3, "16qam": 4}[modulation] / frame_bits) - 2
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


def test_coded_2fsk_decodes_to_the_transmitted_frames() -> None:
    spec = _spec("2fsk", 8, 15.0, inner=CONV, stream_offset=5, offset=0.1)
    g, report = _run(spec)
    assert report.kind == "fsk" and report.label == "2FSK"
    assert report.level is EvidenceLevel.VERIFIED
    truth = _truth_bodies(g)
    passing = [f for f in report.frames if f.crc == "pass"]
    assert len(passing) >= int((1 << 18) / 8 / (2 * FrameSpec().length)) - 2
    indices = [truth.index(f.payload_hex) for f in passing]
    assert indices == list(range(indices[0], indices[0] + len(indices)))
    classify = next(s for s in report.stages if s.id == "classify")
    assert classify.parameters[0].level is EvidenceLevel.VERIFIED
    assert report.search is not None and report.search.shuffled_accepts == 0


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
    ],
    ids=["helical", "802.11"],
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


def _truth_for(g: Generated, spec: FrameSpec) -> list[str]:
    """Hex of each transmitted frame between its sync word and its CRC field."""
    crc = fec_crc_width(spec)
    rows = g.signals[0].framed.reshape(-1, spec.length)
    return [to_bytes(r[len(spec.sync_bits) : -crc]).hex().upper() for r in rows]


def fec_crc_width(spec: FrameSpec) -> int:
    from dsp.synth.bits import CRCS

    return CRCS[spec.crc].width if spec.crc else 0


@pytest.mark.parametrize(
    ("frame", "inner", "offset"),
    [
        # A sync word and CRC the catalogue has never heard of, straight off the modem.
        (FrameSpec(sync="POCSAG", crc="CRC-32", payload_bytes=32), None, 0),
        # Behind the K=7 code, at an arbitrary bit alignment, with a shorter Barker sync.
        (FrameSpec(sync="Barker-13", crc="CRC-16/XMODEM", payload_bytes=24), CONV, 5),
    ],
    ids=["pocsag+crc32", "conv+barker13"],
)
def test_frames_with_an_unknown_sync_word_and_crc_are_found_blind(
    frame: FrameSpec, inner: fec.Convolutional | None, offset: int
) -> None:
    spec = _spec("qpsk", 8, 15.0, frame=frame, inner=inner, stream_offset=offset, offset=0.1)
    g, report = _run(replace(spec, start=10_000, duration=200_000))
    assert report.level is EvidenceLevel.VERIFIED
    truth = _truth_for(g, frame)
    passing = [f for f in report.frames if f.crc == "pass"]
    assert len(passing) >= 60
    assert all(f.payload_hex in truth for f in passing)

    assert report.search is not None and report.search.shuffled_accepts == 0
    accepted = next(r for r in report.search.rows if r.outcome == "accepted")
    assert "blind framing" in accepted.candidate and "held-out" in accepted.statistic
    stage = next(s for s in report.stages if s.id == "frame")
    by_id = {p.id: p for p in stage.parameters}
    assert {"sync_word", "frame_length", "crc", "header"} <= set(by_id)
    assert by_id["frame_length"].value == frame.length
    assert by_id["crc"].value == frame.crc  # the fit matches a catalogued name
    assert by_id["sync_word"].level is EvidenceLevel.VERIFIED
    assert any("constant prefix" in w for w in by_id["sync_word"].warnings)
    assert "counter 16 (+1)" in str(by_id["header"].value)
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
