"""AIS (PLAN M6): the HDLC/CRC check against an independently written generator, and the whole
chain on a GMSK recording (the modulation the plan's M3 stretch item names for it)."""

import math
from typing import Any

import numpy as np
import pytest

from dsp.analyse import analyse
from dsp.detect import detect
from dsp.evidence import EvidenceLevel
from dsp.report import DetectionReport, StageReport
from dsp.synth.chain import Scene, SignalSpec, generate
from dsp.synth.systems import Ais
from dsp.systems import ais

SPS = 16
RATE = 9600.0
FS = RATE * SPS
NOISE_DB = -20.0


def test_the_crc_matches_the_published_check_value() -> None:
    assert ais.crc16_x25(b"123456789") == 0x906E


def test_stuffing_round_trips_and_a_flag_inside_a_frame_is_refused() -> None:
    rng = np.random.default_rng(0)
    bits = np.concatenate([rng.integers(0, 2, 200, dtype=np.uint8), np.ones(23, np.uint8)])
    stuffed = ais.stuff(bits)
    assert len(stuffed) > len(bits)
    restored = ais.destuff(stuffed)
    assert restored is not None and np.array_equal(restored, bits)
    assert ais.destuff(np.array([1, 1, 1, 1, 1, 1, 0], np.uint8)) is None  # six 1s: a flag


def test_nrzi_changes_level_on_a_zero_and_holds_on_a_one() -> None:
    bits = np.array([0, 1, 1, 0, 0, 1], np.uint8)
    levels = ais.nrzi_encode(bits)
    assert levels.tolist() == [0, 1, 1, 1, 0, 1, 1]
    assert np.array_equal(ais.nrzi_decode(levels), bits)
    assert np.array_equal(ais.nrzi_decode(1 - levels), bits)  # polarity does not matter


def _transmission(count: int = 8, **kw: Any) -> Any:
    return Ais(**kw).transmission(count)


def test_the_generator_and_the_check_agree_on_every_packet() -> None:
    found = ais.scan(_transmission(8))
    assert found is not None
    assert found.passes == 8 and found.candidates >= 8
    mmsis = Ais().mmsis
    assert [p.mmsi for p in found.passing[:3]] == list(mmsis)
    assert {p.message_type for p in found.passing} == {1}
    assert found.p_value < 1e-30
    assert all(p.length_bits == 184 for p in found.passing)  # 168 message bits and the FCS


def test_a_mirrored_stream_gives_the_same_packets() -> None:
    bits = _transmission(6)
    found = ais.scan(1 - bits)
    assert found is not None and found.passes == 6


def test_a_corrupted_packet_fails_its_crc_and_the_rest_still_count() -> None:
    bits = np.array(_transmission(8), copy=True)
    # damage one bit well inside the fourth packet (a packet is about 230 transmitted bits)
    at = 3 * 232 + 120
    bits[at : at + 1] ^= 1
    found = ais.scan(bits)
    assert found is not None
    assert found.passes < 8 and found.passes >= 5


def test_one_packet_is_not_enough_to_clear_the_threshold() -> None:
    assert ais.scan(_transmission(1)) is None


def test_random_and_idle_streams_are_not_ais_in_two_thousand_trials() -> None:
    rng = np.random.default_rng(3)
    for _ in range(2000):
        assert ais.scan(rng.integers(0, 2, 20_000, dtype=np.uint8)) is None
    for pattern in (np.zeros(20_000), np.ones(20_000), np.tile([0, 1], 10_000)):
        assert ais.scan(pattern.astype(np.uint8)) is None


class Memory:
    def __init__(self, x: Any) -> None:
        self.x = np.asarray(x)
        self.num_samples = len(self.x)

    def read(self, start: int, count: int) -> Any:
        return self.x[start : start + count]


def _gmsk_report(esn0: float, *, mirror: bool = False, corrupt: float = 0.0) -> DetectionReport:
    power = NOISE_DB + esn0 - 10 * math.log10(SPS)
    spec = SignalSpec(
        modulation="2fsk",
        sps=SPS,
        fsk_index=0.5,
        fsk_bt=0.4,  # GMSK as AIS uses it: index one half, Gaussian filter BT 0.4
        power_db=power,
        frame=None,
        system=Ais(corrupt=corrupt),
        offset=0.05,
        start=10_000,
        duration=200_000,
    )
    g = generate(Scene(samples=1 << 18, signals=(spec,), noise_db=NOISE_DB), 4)
    x = np.conj(g.samples) if mirror else g.samples
    source = Memory(x)
    detections = detect(source, real=False).detections
    main = max(detections, key=lambda d: (d.stop - d.start) * (d.high - d.low))
    return analyse(source, main, sample_rate=FS)


def _stage(report: DetectionReport, stage_id: str) -> StageReport:
    return next(s for s in report.stages if s.id == stage_id)


def test_a_gmsk_ais_recording_is_verified_through_the_chain() -> None:
    report = _gmsk_report(18.0)
    system = next(p for p in _stage(report, "match").parameters if p.id == "system")
    assert system.level is EvidenceLevel.VERIFIED and system.value == "AIS"
    assert system.proof is not None and system.proof.kind == "crc"
    assert report.level is EvidenceLevel.VERIFIED and "AIS" in report.headline
    # The symbol rate came from the MSK line pair on a convention (index 0.5): the system's own
    # CRC passing on the bits demodulated at that rate settles it, so it is promoted.
    rate = next(p for p in _stage(report, "estimate").parameters if p.id == "symbol_rate")
    assert rate.level is EvidenceLevel.VERIFIED and rate.convention is None
    assert rate.value == pytest.approx(RATE, rel=2e-3)
    assert any("Promoted from HYPOTHESIS" in line for line in rate.evidence)
    messages = next(p for p in _stage(report, "match").parameters if p.id == "ais_messages")
    assert messages.level is EvidenceLevel.HYPOTHESIS and messages.convention
    shown = " ".join(messages.evidence)
    for mmsi in Ais().mmsis:
        assert f"MMSI {mmsi:09d}" in shown
    assert report.frames and report.frames[0].sync_word == "7E"
    # At 18 dB the Gaussian filter's intersymbol interference leaves about 1 % raw bit errors, so
    # only some packets pass; the check needs two and the p-value says how far past chance it is.
    passing = sum(f.crc == "pass" for f in report.frames)
    assert passing >= 4


def test_every_packet_passes_when_the_gmsk_is_clean_enough() -> None:
    report = _gmsk_report(26.0)
    passing = sum(f.crc == "pass" for f in report.frames)
    assert passing >= 0.9 * len(report.frames)


def test_a_mirrored_gmsk_recording_is_verified_too() -> None:
    report = _gmsk_report(18.0, mirror=True)
    system = next(p for p in _stage(report, "match").parameters if p.id == "system")
    assert system.level is EvidenceLevel.VERIFIED and system.value == "AIS"


def test_ais_is_not_claimed_for_a_noisy_recording_that_does_not_decode() -> None:
    report = _gmsk_report(2.0)
    system = next(p for p in _stage(report, "match").parameters if p.id == "system")
    assert system.level is not EvidenceLevel.VERIFIED
    assert report.level is not EvidenceLevel.VERIFIED


# -- where the MSK candidate comes from and where it must not appear ---------------------------


def _channel(index: float, bt: float, esn0: float = 20.0, **kw: Any) -> Any:
    from dsp.channel import channelise

    power = NOISE_DB + esn0 - 10 * math.log10(SPS)
    spec = SignalSpec(
        modulation="2fsk",
        sps=SPS,
        fsk_index=index,
        fsk_bt=bt,
        power_db=power,
        offset=0.05,
        start=10_000,
        duration=200_000,
        **kw,
    )
    g = generate(Scene(samples=1 << 18, signals=(spec,), noise_db=NOISE_DB), 4)
    source = Memory(g.samples)
    main = max(
        detect(source, real=False).detections, key=lambda d: (d.stop - d.start) * d.bandwidth
    )
    return channelise(source, main)


def test_gmsk_gets_the_line_pair_candidate_stated_as_a_convention() -> None:
    from dsp.analyse import _fsk_candidates

    channel = _channel(0.5, 0.4, frame=None)
    candidates = _fsk_candidates(channel.samples)
    msk = [c for c in candidates if c.assumption]
    assert len(msk) == 1 and "index 0.5" in str(msk[0].assumption)
    true_rate = channel.decimation / SPS
    assert msk[0].normalised_rate == pytest.approx(true_rate, rel=1e-3)


@pytest.mark.parametrize(("index", "bt"), [(1.0, 0.0), (0.5, 0.0)])
def test_a_pair_the_comb_already_explains_adds_no_candidate(index: float, bt: float) -> None:
    """Index 1 (a pair 2 R apart) and an abrupt index-0.5 signal (the comb finds R) are the
    comb's candidates already: no extra trial, no extra hypothesis in the count."""
    from dsp.analyse import _fsk_candidates

    channel = _channel(index, bt, frame=None)
    assert not [c for c in _fsk_candidates(channel.samples) if c.assumption]


def test_noise_gets_no_line_pair_candidate() -> None:
    from dsp.analyse import _fsk_candidates

    rng = np.random.default_rng(1)
    for _ in range(200):
        x = rng.standard_normal(1 << 15) + 1j * rng.standard_normal(1 << 15)
        assert not [c for c in _fsk_candidates(x) if c.assumption]
