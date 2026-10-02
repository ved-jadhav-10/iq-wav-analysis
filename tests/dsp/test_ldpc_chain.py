"""A catalogued LDPC code through the decode chain: a dsp.synth recording, encoded by the
generator-side encoder, comes out as the exact transmitted frames, VERIFIED by the CRC alone
(PLAN M5)."""

import math
from dataclasses import replace
from typing import Any

import numpy as np
import pytest

from dsp.analyse import analyse
from dsp.detect import detect
from dsp.evidence import EvidenceLevel
from dsp.fec import ldpc
from dsp.report import DetectionReport
from dsp.synth import fec
from dsp.synth.bits import FrameSpec, to_bytes
from dsp.synth.chain import Generated, Scene, SignalSpec, generate

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


@pytest.mark.parametrize(
    ("name", "modulation", "offset", "esn0"),
    [
        ("IEEE 802.11n n=648 r1/2", "qpsk", 123, 10.0),
        ("IEEE 802.11n n=648 r5/6", "qpsk", 0, 14.0),
        ("CCSDS TC n=256 k=128", "bpsk", 77, 8.0),
    ],
)
def test_ldpc_stream_decodes_to_the_transmitted_frames(
    name: str, modulation: str, offset: int, esn0: float
) -> None:
    code = ldpc.by_name(name)
    spec = _spec(modulation, 8, esn0, inner=fec.standard_ldpc(code), stream_offset=offset)
    spec = replace(spec, start=10_000, duration=230_000)
    g, report = _run(spec)
    assert report.level is EvidenceLevel.VERIFIED
    assert code.name in report.headline
    truth = _truth_bodies(g)
    passing = [f for f in report.frames if f.crc == "pass"]
    # The burst carries only part of the generated stream: every whole frame in it decodes.
    bits_per_symbol = 2 if modulation == "qpsk" else 1
    in_burst = (230_000 // 8) * bits_per_symbol * code.k // code.n // FrameSpec().length
    assert len(passing) >= in_burst - 2
    assert {f.payload_hex for f in passing} <= set(truth)
