"""Write the demo SigMF scene(s) (PROTOTYPE_PLAN P1) to data/demo/ from a fixed seed, then verify
them the way the backend does: open, detect, analyse each detection, and check the coded PSK
signals' passing frames against the exact transmitted payload bytes.

All three files are synthetic (dsp.synth, truth in the SigMF annotations and a .truth.json):
  - scene.sigmf-meta, PROTOTYPE_PLAN's demo target: QPSK + BPSK (both conv K=7 r1/2, CCSDS ASM,
    CRC-16) that must reach VERIFIED, one uncoded/unframed QPSK that must not, and an FM signal
    that must be labelled analog.
  - scene_widen.sigmf-meta, P2's chains: 8PSK through a 16x36 block interleaver, and QPSK with
    an outer RS(255,223) code, both VERIFIED.
  - scene_fsk.sigmf-meta: a lone coded 2-FSK signal, VERIFIED.

Run: uv run python tools/make_demo.py
"""

import json
import math
import sys
from pathlib import Path
from typing import NotRequired, TypedDict

from dsp.analyse import analyse
from dsp.detect import detect
from dsp.evidence import EvidenceLevel
from dsp.ingest.dispatch import open_path
from dsp.synth import fec
from dsp.synth import interleave as il
from dsp.synth.bits import FrameSpec, to_bytes
from dsp.synth.chain import Generated, Scene, SignalSpec, generate, write_sigmf


class TruthEntry(TypedDict):
    label: str
    modulation: str
    kind: str
    offsetHz: float
    expectedLevel: str
    expectPayloadHex: NotRequired[list[str]]
    reason: NotRequired[str]


SEED = 90210
NOISE_DB = -20.0
SAMPLE_RATE = 1_000_000.0
SAMPLES = 1 << 20
OUT_DIR = Path("data/demo")
CONV = fec.Convolutional(7, fec.K7)


def _spec(modulation: str, sps: int, esn0_db: float, **kw: object) -> SignalSpec:
    """Es/N0 = SNR + 10 log10(sps), so power_db follows from the target Es/N0 (matches
    tests/dsp/test_slice.py's `_spec`)."""
    power = NOISE_DB + esn0_db - 10 * math.log10(sps)
    return SignalSpec(modulation=modulation, sps=sps, power_db=power, **kw)  # type: ignore[arg-type]


def _truth_bodies(g: Generated, index: int, frame: FrameSpec) -> list[str]:
    """Hex of each transmitted frame's payload+counter between its sync word and its CRC,
    matching what `dsp.analyse.analyse` reports as `Frame.payload_hex`."""
    rows = g.signals[index].framed.reshape(-1, frame.length)
    crc_bits = 16 if frame.crc else 0
    return [to_bytes(r[len(frame.sync_bits) : len(r) - crc_bits]).hex().upper() for r in rows]


def _frames_truth(g: Generated, index: int, label: str, modulation: str, hz: float) -> TruthEntry:
    return {
        "label": label,
        "modulation": modulation,
        "kind": "fsk" if "fsk" in modulation else "psk",
        "offsetHz": hz,
        "expectedLevel": "VERIFIED",
        "expectPayloadHex": _truth_bodies(g, index, FrameSpec()),
    }


def build_main() -> tuple[Generated, Scene, list[TruthEntry]]:
    # Every signal narrow enough that dsp.channel decimates (and so filters) its channel: at
    # decimation 1 the channel is only mixed, not filtered, so neighbours would leak in. Uneven
    # spacing and staggered bursts: evenly spaced, equally wide, co-temporal signals are
    # what dsp.detect's M-FSK tone-comb merge looks for.
    qpsk = _spec("qpsk", 20, 15.0, inner=CONV, offset=-360_000.0 / SAMPLE_RATE, stream_offset=41)
    bpsk = _spec(
        "bpsk",
        32,
        15.0,
        inner=CONV,
        offset=-120_000.0 / SAMPLE_RATE,
        stream_offset=17,
        start=60_000,
        duration=900_000,
    )
    undecodable = _spec(
        "qpsk",
        24,
        15.0,
        frame=None,
        offset=80_000.0 / SAMPLE_RATE,
        stream_offset=5,
        start=150_000,
        duration=700_000,
    )
    fm = SignalSpec(
        modulation="fm",
        power_db=NOISE_DB + 25.0,
        offset=330_000.0 / SAMPLE_RATE,
        fm_deviation=0.015,
    )
    scene = Scene(
        samples=SAMPLES,
        signals=(qpsk, bpsk, undecodable, fm),
        noise_db=NOISE_DB,
        sample_rate=SAMPLE_RATE,
    )
    g = generate(scene, SEED)
    truth: list[TruthEntry] = [
        _frames_truth(g, 0, "QPSK", "qpsk", -360_000.0),
        _frames_truth(g, 1, "BPSK", "bpsk", -120_000.0),
        {
            # Uncoded and unframed: a symbol rate is found and the symbols demodulate, but no
            # catalogued code or sync word confirms anything, so the FEC stage's code is UNKNOWN.
            "label": "Unknown",
            "modulation": "qpsk (uncoded, unframed)",
            "kind": "psk",
            "offsetHz": 80_000.0,
            "expectedLevel": "not VERIFIED",
            "reason": "no sync word, no CRC: the FEC stage's code Parameter is UNKNOWN",
        },
        {
            "label": "FM",
            "modulation": "fm",
            "kind": "analog",
            "offsetHz": 330_000.0,
            "expectedLevel": "not VERIFIED",
            "reason": "analog signals skip the digital chain",
        },
    ]
    return g, scene, truth


def build_widen() -> tuple[Generated, Scene, list[TruthEntry]]:
    """PROTOTYPE_PLAN P2's chains: 8PSK through a block interleaver, and QPSK with an outer
    RS(255,223) code - both conv K=7 r1/2 inside, CCSDS ASM + CRC-16 frames."""
    psk8 = _spec(
        "8psk",
        20,
        16.0,
        inner=CONV,
        interleaver=il.Block(16, 36),
        offset=-40_000.0 / SAMPLE_RATE,
        stream_offset=301,
        start=40_000,
        duration=950_000,
    )
    rs = _spec(
        "qpsk",
        24,
        15.0,
        inner=CONV,
        outer=fec.RS_CCSDS,
        offset=270_000.0 / SAMPLE_RATE,
        stream_offset=77,
        start=120_000,
        duration=880_000,
    )
    scene = Scene(samples=SAMPLES, signals=(psk8, rs), noise_db=NOISE_DB, sample_rate=SAMPLE_RATE)
    g = generate(scene, SEED + 1)
    truth: list[TruthEntry] = [
        _frames_truth(g, 0, "8PSK", "8psk + block 16x36", -40_000.0),
        _frames_truth(g, 1, "QPSK", "qpsk + RS(255,223)", 270_000.0),
    ]
    return g, scene, truth


def build_fsk() -> tuple[Generated, Scene, list[TruthEntry]]:
    """2-FSK on its own: its symbol-rate estimate is only reliable on an undecimated channel
    with nothing else in it (see PROTOTYPE_PLAN P4)."""
    fsk = _spec("2fsk", 8, 15.0, inner=CONV, offset=100_000.0 / SAMPLE_RATE, stream_offset=5)
    scene = Scene(samples=1 << 18, signals=(fsk,), noise_db=NOISE_DB, sample_rate=SAMPLE_RATE)
    g = generate(scene, SEED + 2)
    return g, scene, [_frames_truth(g, 0, "2FSK", "2fsk", 100_000.0)]


def write_and_verify(stem: Path, g: Generated, scene: Scene, truth: list[TruthEntry]) -> bool:
    stem.parent.mkdir(parents=True, exist_ok=True)
    path = write_sigmf(stem, g, scene, "cf32_le")
    truth_path = stem.with_suffix(".truth.json")
    truth_path.write_text(json.dumps(truth, indent=2), encoding="utf-8")
    print(f"\nwrote {path} and {path.with_suffix('.sigmf-data')}")
    print(f"wrote {truth_path}")
    for t in truth:
        n_frames = len(t.get("expectPayloadHex") or [])
        extra = f", {n_frames} truth frames" if n_frames else ""
        print(f"  {t['label']:8s} @ {t['offsetHz']:+.0f} Hz  {t['kind']:8s}{extra}")

    print("verifying: open -> detect -> analyse (as the backend does)")
    (opened,) = open_path(path)
    with opened.recording.reader() as reader:
        detections = detect(reader, real=False).detections
    print(f"{len(detections)} detection(s)")
    if len(detections) != len(truth):
        print(f"  FAIL: expected {len(truth)} detections, got {len(detections)}")
        return False
    ok = True
    for i, d in enumerate(detections):
        with opened.recording.reader() as reader:
            report = analyse(reader, d, sample_rate=SAMPLE_RATE)
        centre_hz = (d.low + d.high) / 2 * SAMPLE_RATE
        nearest = min(truth, key=lambda t: abs(t["offsetHz"] - centre_hz))
        passing = [f for f in report.frames if f.crc == "pass"]
        print(
            f"  detection {i}: centre {centre_hz:+.0f} Hz (nearest truth: {nearest['label']}) "
            f"label={report.label!r} kind={report.kind} level={report.level.value} "
            f"frames={len(report.frames)} passing={len(passing)}"
        )
        expect_hex = nearest.get("expectPayloadHex")
        if nearest["kind"] != report.kind or (expect_hex and nearest["label"] != report.label):
            print(f"    FAIL: expected {nearest['label']} ({nearest['kind']})")
            ok = False
        if expect_hex:
            bad = [f.payload_hex for f in passing if f.payload_hex not in expect_hex]
            if not passing:
                print(f"    FAIL: expected passing frames for {nearest['label']}, got none")
                ok = False
            elif bad:
                print(f"    FAIL: {len(bad)} passing frame(s) don't match the truth payload hex")
                ok = False
            else:
                print(f"    OK: all {len(passing)} passing frame(s) match the truth payload hex")
        elif nearest["label"] in ("Unknown", "FM"):
            if report.level is EvidenceLevel.VERIFIED:
                print(f"    FAIL: {nearest['label']} unexpectedly reached VERIFIED")
                ok = False
            else:
                print(f"    OK: {nearest['label']} did not reach VERIFIED ({report.level.value})")
    return ok


def main() -> None:
    print(f"seed={SEED} sample_rate={SAMPLE_RATE:g} samples={SAMPLES}")
    ok_main = write_and_verify(OUT_DIR / "scene", *build_main())
    ok_widen = write_and_verify(OUT_DIR / "scene_widen", *build_widen())
    ok_fsk = write_and_verify(OUT_DIR / "scene_fsk", *build_fsk())
    if not (ok_main and ok_widen and ok_fsk):
        print("\nSOME CHECKS FAILED - see above")
        sys.exit(1)
    print("\nall checks passed")


if __name__ == "__main__":
    main()
