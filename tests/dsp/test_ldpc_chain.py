"""A catalogued LDPC code through the decode chain: a dsp.synth recording, encoded by the
generator-side encoder, comes out as the exact transmitted frames, VERIFIED by the CRC alone
(PLAN M5), with the evidence its code claim rests on; and streams that are not LDPC (noise,
uncoded and convolutionally coded data) are never accepted as such."""

import math
import re
from dataclasses import replace
from typing import Any

import numpy as np
import pytest

from dsp import analyse as chain
from dsp.analyse import analyse
from dsp.detect import detect
from dsp.evidence import EvidenceLevel, Parameter
from dsp.fec import ldpc, rs
from dsp.framing import CRCS, SYNC_WORDS
from dsp.report import DetectionReport
from dsp.scramble import DESCRAMBLERS
from dsp.synth import fec
from dsp.synth.bits import FrameSpec, to_bytes
from dsp.synth.chain import Generated, Scene, SignalSpec, generate
from dsp.synth.impair import Impairments

NOISE_DB = -20.0


class Memory:
    def __init__(self, x: Any) -> None:
        self.x = np.asarray(x)
        self.num_samples = len(self.x)

    def read(self, start: int, count: int) -> Any:
        return self.x[start : start + count]


def _run(spec: SignalSpec, seed: int = 7) -> tuple[Generated, DetectionReport]:
    g = generate(Scene(samples=1 << 18, signals=(spec,), noise_db=NOISE_DB), seed)
    source = Memory(g.samples)
    detections = detect(source, real=False).detections
    assert detections, "the signal must be detected"
    main = max(detections, key=lambda d: (d.stop - d.start) * (d.high - d.low))
    return g, analyse(source, main)


def _spec(modulation: str, sps: int, esn0_db: float, **kw: Any) -> SignalSpec:
    power = NOISE_DB + esn0_db - 10 * math.log10(sps)
    return SignalSpec(modulation=modulation, sps=sps, power_db=power, **kw)


def _truth_bodies(g: Generated) -> list[str]:
    spec = FrameSpec()
    rows = g.signals[0].framed.reshape(-1, spec.length)
    return [to_bytes(r[len(spec.sync_bits) : -16]).hex().upper() for r in rows]


def _code_parameter(report: DetectionReport) -> Parameter:
    stage = next(s for s in report.stages if s.id == "fec")
    return next(p for p in stage.parameters if p.id == "code")


# name, modulation, stream offset (coded bits skipped), Es/N0 dB, burst samples. The first three
# are long bursts; the other unpunctured codes run on shorter ones to keep the chain's cost down.
CASES = [
    ("IEEE 802.11n n=648 r1/2", "qpsk", 123, 10.0, 230_000),
    ("IEEE 802.11n n=648 r5/6", "qpsk", 0, 14.0, 230_000),
    ("CCSDS TC n=256 k=128", "bpsk", 77, 8.0, 230_000),
    ("IEEE 802.11n n=648 r2/3", "qpsk", 31, 12.0, 120_000),
    ("IEEE 802.11n n=648 r3/4", "qpsk", 5, 13.0, 120_000),
    ("CCSDS TC n=128 k=64", "bpsk", 9, 8.0, 100_000),
    ("CCSDS TC n=512 k=256", "bpsk", 301, 8.0, 100_000),
]


@pytest.mark.parametrize(("name", "modulation", "offset", "esn0", "samples"), CASES)
def test_ldpc_stream_decodes_to_the_transmitted_frames(
    name: str, modulation: str, offset: int, esn0: float, samples: int
) -> None:
    code = ldpc.by_name(name)
    spec = _spec(modulation, 8, esn0, inner=fec.standard_ldpc(code), stream_offset=offset)
    spec = replace(spec, start=10_000, duration=samples)
    g, report = _run(spec)
    assert report.level is EvidenceLevel.VERIFIED
    assert code.name in report.headline
    truth = _truth_bodies(g)
    passing = [f for f in report.frames if f.crc == "pass"]
    # The burst carries only part of the generated stream: every whole frame in it decodes.
    bits_per_symbol = 2 if modulation == "qpsk" else 1
    in_burst = (samples // 8) * bits_per_symbol * code.k // code.n // FrameSpec().length
    assert len(passing) >= in_burst - 2
    assert {f.payload_hex for f in passing} <= set(truth)

    # The code claim is VERIFIED by the frame CRC and says what it rests on.
    param = _code_parameter(report)
    assert param.value == code.name and param.level is EvidenceLevel.VERIFIED
    assert param.proof is not None and param.proof.kind == "crc"
    evidence = " ".join(param.evidence)
    assert f"n = {code.n}, k = {code.k}, {code.transmitted} bits per block" in evidence
    screen = re.search(r"ranked (\d+) alignments \((\d+) window\(s\) x (\d+) offsets\)", evidence)
    assert screen is not None and int(screen[3]) == code.transmitted
    assert int(screen[1]) == int(screen[2]) * code.transmitted
    assert re.search(r"z = [\d.]+ at this one against a gate of [\d.]+", evidence)
    assert re.search(r"brought \d+ of the 4 blocks it scanned to a valid code word", evidence)
    blocks = re.search(r"(\d+) of (\d+) whole blocks decoded to a valid code word", evidence)
    # Every block of the burst decodes, give or take its ragged ends; the stream may run on past
    # the burst into noise, which is what the blocks beyond that count are.
    burst_blocks = (samples // 8) * bits_per_symbol // code.transmitted
    assert blocks is not None and int(blocks[1]) >= burst_blocks - 2 >= 8
    assert re.search(
        r"the first \d+ soft bits and a trailing partial block of \d+ are dropped", evidence
    )
    polarity = (
        "Every parity check has even weight"
        if not (code.row_weights % 2).any()
        else ("Some parity checks have odd weight")
    )
    assert polarity in evidence

    assert report.search is not None and report.search.shuffled_accepts == 0
    assert report.search.shuffled_runs > 0
    accepted = [r for r in report.search.rows if r.outcome == "accepted"]
    assert len(accepted) == 1 and accepted[0].layer == "FEC"
    assert code.name in accepted[0].candidate and "alignment" in accepted[0].candidate


def test_a_stream_inverted_by_the_carrier_phase_still_decodes_for_an_odd_weight_code() -> None:
    """Every check of 802.11n r2/3 has odd weight, so a complemented stream is not a code word:
    rotating the carrier by 180 degrees must be undone by the phase search, and the decode is
    VERIFIED either way."""
    code = ldpc.by_name("IEEE 802.11n n=648 r2/3")
    assert (code.row_weights % 2).all()
    rotations: list[str] = []
    for phase in (0.0, math.pi):
        spec = _spec(
            "bpsk",
            8,
            8.0,
            inner=fec.standard_ldpc(code),
            stream_offset=40,
            impairments=Impairments(phase=phase),
        )
        g, report = _run(replace(spec, start=10_000, duration=100_000))
        assert report.level is EvidenceLevel.VERIFIED and code.name in report.headline
        passing = [f for f in report.frames if f.crc == "pass"]
        assert len(passing) >= 10 and {f.payload_hex for f in passing} <= set(_truth_bodies(g))
        sync = next(s for s in report.stages if s.id == "sync")
        rotations.append(str(next(p for p in sync.parameters if p.id == "rotation").value))
    assert rotations[0] != rotations[1]  # the phase search took the half turn out


@pytest.mark.parametrize(
    ("name", "complement_is_a_code_word"),
    [
        ("IEEE 802.11n n=648 r2/3", False),
        ("IEEE 802.11n n=648 r5/6", True),
        ("CCSDS TC n=128 k=64", True),
    ],
)
def test_a_complemented_branch_aligns_only_for_a_code_that_allows_it(
    name: str, complement_is_a_code_word: bool
) -> None:
    """The chain tries every rotation of the LDPC cell as it is: the 180 degree branch of an
    odd-weight code finds no alignment, one of an even-weight code finds the same one."""
    code = ldpc.by_name(name)
    rng = np.random.default_rng(5)
    words = ldpc.encode(code, rng.integers(0, 2, (6, code.k), dtype=np.uint8)).ravel()
    stream = 8.0 * (1.0 - 2.0 * np.concatenate([rng.integers(0, 2, 50), words]))
    upright = chain._ldpc_cells(("BPSK", 0, stream))  # pyright: ignore[reportPrivateUsage]
    inverted = chain._ldpc_cells(("BPSK", 180, -stream))  # pyright: ignore[reportPrivateUsage]

    def aligned(chains: list[Any]) -> set[int]:
        return {
            c.alignment
            for c in chains
            if c.ldpc is code and c.ldpc_run is not None and c.ldpc_run.alignment.found
        }

    assert aligned(upright) == {50 % code.transmitted}
    assert aligned(inverted) == ({50 % code.transmitted} if complement_is_a_code_word else set())
    if not complement_is_a_code_word:
        rows = [c for c in inverted if c.ldpc is code]
        assert len(rows) == 1 and rows[0].candidate.endswith("no alignment passed")
        assert rows[0].p_value is None and rows[0].frames is None


def test_the_search_counts_every_ldpc_block_alignment(monkeypatch: pytest.MonkeyPatch) -> None:
    codes = chain.LDPC_CODES
    assert codes and all(c.punctured == 0 for c in codes)
    with_codes = chain._search(iter(()), 3, {}).tried  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(chain, "LDPC_CODES", ())
    without = chain._search(iter(()), 3, {}).tried  # pyright: ignore[reportPrivateUsage]
    per_alignment = (
        3 * len(SYNC_WORDS) * (1 + len(DESCRAMBLERS)) * len(CRCS) * (1 + rs.GRID_HYPOTHESES)
    )
    assert with_codes - without == sum(c.n for c in codes) * per_alignment


def _assert_no_ldpc_accepted(report: DetectionReport) -> None:
    assert report.level is not EvidenceLevel.VERIFIED and not report.frames
    assert report.search is not None
    assert not any(r.outcome == "accepted" for r in report.search.rows)
    assert report.search.shuffled_accepts == 0
    param = _code_parameter(report)
    assert param.value is None and param.level is EvidenceLevel.UNKNOWN
    text = " ".join(param.evidence)
    # It names the catalogued LDPC codes it tried, says what the screen is and what is not tried.
    assert "IEEE 802.11n n=648 r1/2" in text and "r5/6" in text
    assert "CCSDS TC n=128 k=64" in text and "n=512 k=256" in text
    assert "soft-syndrome" in text and "not proof of absence" in text
    assert "CCSDS TM LDPC codes are not yet tried" in text
    assert "catalogued LDPC" in param.method
    rows = [r for r in report.search.rows if "802.11n" in r.candidate or "CCSDS TC" in r.candidate]
    assert rows
    for row in rows:
        assert row.layer == "FEC" and row.outcome == "rejected" and row.p_value is None
        assert row.candidate.endswith("no alignment passed")
        assert "Soft-syndrome z" in row.statistic and "gate" in row.statistic
        assert "none decoded" in row.statistic or "blocks converged" in row.statistic
        assert row.reason.startswith("No alignment passed")


def test_uncoded_random_bits_are_never_taken_for_an_ldpc_code() -> None:
    spec = _spec("qpsk", 8, 15.0, frame=None)
    _, report = _run(replace(spec, start=10_000, duration=100_000))
    _assert_no_ldpc_accepted(report)


def test_a_convolutionally_coded_stream_is_never_taken_for_an_ldpc_code() -> None:
    """A K=9 code outside the catalogue, no frame: no LDPC alignment passes."""
    spec = _spec("qpsk", 8, 15.0, frame=None, inner=fec.Convolutional(9, (0o561, 0o753)))
    _, report = _run(replace(spec, start=10_000, duration=100_000))
    _assert_no_ldpc_accepted(report)


def test_the_shuffled_bit_control_also_runs_the_alignment_screen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A chain accepted on an LDPC code is checked on shuffled bits through the screen that chose
    the code too: each shuffled run in which it still finds an alignment counts as an accept."""
    code = ldpc.by_name("CCSDS TC n=128 k=64")
    llr = np.random.default_rng(1).standard_normal(8 * code.transmitted)
    candidate = chain._Chain("BPSK", 0, None, 0, None, llr, None, ldpc=code)  # pyright: ignore[reportPrivateUsage]
    calls: list[int] = []

    def fires(stream: Any, standard: Any) -> ldpc.Alignment:
        calls.append(len(stream))
        return ldpc.Alignment(0, 0.0, True, 1, 4, "soft syndrome", 0.0)

    shuffled = chain._shuffled_accepts  # pyright: ignore[reportPrivateUsage]
    assert shuffled(candidate, 1e-9) == 0  # the real screen finds nothing in shuffled noise
    monkeypatch.setattr(chain.ldpc_codes, "find_alignment", fires)
    assert shuffled(candidate, 1e-9) == chain.SHUFFLED_RUNS
    assert calls == [len(llr)] * chain.SHUFFLED_RUNS
