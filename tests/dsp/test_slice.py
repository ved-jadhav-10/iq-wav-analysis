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


def test_repetition_coded_frames_are_not_verified() -> None:
    _, report = _run(_spec("qpsk", 8, 15.0, inner=fec.Repetition(3), offset=0.05))
    assert report.level is not EvidenceLevel.VERIFIED
    assert all(f.crc != "pass" for f in report.frames)


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
