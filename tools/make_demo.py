"""Write the synthetic sample recordings to data/demo/ from a fixed seed, then verify
them the way the backend does: open, detect, analyse each detection, and check the coded
signals' passing frames against the exact transmitted payload bytes.

All files are synthetic (dsp.synth, truth in a .truth.json and, for SigMF, the annotations):
  - scene.sigmf-meta: QPSK + BPSK (both conv K=7 r1/2, CCSDS ASM,
    CRC-16) that must reach VERIFIED, one uncoded/unframed QPSK that must not, and an FM signal
    that must be labelled analog.
  - scene_widen.sigmf-meta: 8PSK through a 16x36 block interleaver, and QPSK with
    an outer RS(255,223) code, both VERIFIED.
  - scene_fsk.sigmf-meta: a lone coded 2-FSK signal, VERIFIED.
  - scene_ldpc.sigmf-meta: a lone QPSK signal under the IEEE 802.11n n=648 rate-1/2 LDPC code,
    identified from the catalogue and VERIFIED by its frame CRC.
  - scene_coverage.sigmf-meta: 16QAM through a 16x36 helical interleaver, QPSK through a
    convolutional (Forney) interleaver, and QPSK under a K=9 code outside the catalogue (found
    blind); frames carry ASCII text. All VERIFIED.
  - scene_fsk4.sigmf-meta: a lone coded 4-FSK signal with ASCII frames, VERIFIED (alone, as
    M-FSK's symbol-rate estimate is an Open gate on crowded channels).
  - scene_raw.cf32: headerless complex float32, no sample rate anywhere. It must open with the
    rate UNKNOWN; entering 1 MS/s must analyse its coded QPSK signal to VERIFIED.
  - scene_wav.wav: a 48 kHz 16-bit stereo IQ WAV (I left, Q right) with a coded QPSK signal; the
    rate is MEASURED from the header and the frames VERIFIED.

Every check must pass or the script exits non-zero. The first four files are byte-identical from
run to run (fixed seeds); do not change their builders.

Run: uv run python tools/make_demo.py
"""

import json
import math
import sys
import tempfile
import time
import wave
from pathlib import Path
from typing import Any, NotRequired, TypedDict

import numpy as np
from fastapi.testclient import TestClient

from backend.app import create_app
from dsp.analyse import analyse
from dsp.detect import detect
from dsp.evidence import EvidenceLevel
from dsp.fec import ldpc
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
    """Deeper chains: 8PSK through a block interleaver, and QPSK with an outer
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
    with nothing else in it (an Open gate in PLAN §0)."""
    fsk = _spec("2fsk", 8, 15.0, inner=CONV, offset=100_000.0 / SAMPLE_RATE, stream_offset=5)
    scene = Scene(samples=1 << 18, signals=(fsk,), noise_db=NOISE_DB, sample_rate=SAMPLE_RATE)
    g = generate(scene, SEED + 2)
    return g, scene, [_frames_truth(g, 0, "2FSK", "2fsk", 100_000.0)]


def build_ldpc() -> tuple[Generated, Scene, list[TruthEntry]]:
    """QPSK under a catalogued LDPC code (802.11n, n = 648, rate 1/2), 10 dB Es/N0."""
    inner = fec.standard_ldpc(ldpc.by_name("IEEE 802.11n n=648 r1/2"))
    qpsk = _spec(
        "qpsk",
        8,
        10.0,
        inner=inner,
        offset=150_000.0 / SAMPLE_RATE,
        stream_offset=123,
        start=10_000,
        duration=230_000,
    )
    scene = Scene(samples=1 << 18, signals=(qpsk,), noise_db=NOISE_DB, sample_rate=SAMPLE_RATE)
    g = generate(scene, SEED + 3)
    return g, scene, [_frames_truth(g, 0, "QPSK", "qpsk + LDPC 802.11n r1/2", 150_000.0)]


def build_coverage() -> tuple[Generated, Scene, list[TruthEntry]]:
    """One band that shows more of the requirements: 16QAM through a helical interleaver, QPSK
    through a convolutional (Forney) interleaver, and QPSK under a K=9 convolutional code that is
    not in the catalogue (found blind). Frames carry ASCII text. Three signals, not four: four
    similar, nearly evenly spaced, co-temporal signals look like a 4-FSK tone comb to
    dsp.detect, so the 4-FSK signal is its own scene (`build_fsk4`)."""
    qam = _spec(
        "16qam",
        20,
        17.0,
        inner=CONV,
        interleaver=il.Helical(16, 36),
        offset=-250_000.0 / SAMPLE_RATE,
        stream_offset=301,
        text="SANKET 16QAM HELICAL FRAME ",
    )
    qpsk = _spec(
        "qpsk",
        24,
        15.0,
        inner=CONV,
        interleaver=il.Convolutional(5, 2),
        offset=60_000.0 / SAMPLE_RATE,
        stream_offset=7,
        start=50_000,
        duration=900_000,
        text="SANKET QPSK FORNEY FRAME ",
    )
    k9 = _spec(
        "qpsk",
        28,
        15.0,
        inner=fec.Convolutional(9, (0o561, 0o753)),
        offset=330_000.0 / SAMPLE_RATE,
        stream_offset=37,
        start=150_000,
        duration=850_000,
        text="SANKET K9 BLIND FRAME ",
    )
    scene = Scene(
        samples=SAMPLES, signals=(qam, qpsk, k9), noise_db=NOISE_DB, sample_rate=SAMPLE_RATE
    )
    g = generate(scene, SEED + 10)
    truth: list[TruthEntry] = [
        _frames_truth(g, 0, "16QAM", "16qam + helical 16x36", -250_000.0),
        _frames_truth(g, 1, "QPSK", "qpsk + convolutional interleaver I=5 M=2", 60_000.0),
        _frames_truth(g, 2, "QPSK", "qpsk + K=9 r1/2 (found blind)", 330_000.0),
    ]
    return g, scene, truth


def build_fsk4() -> tuple[Generated, Scene, list[TruthEntry]]:
    """4-FSK on its own, for the same reason as `build_fsk`: M-FSK's symbol-rate estimate fails
    on a decimated channel with neighbours (an Open gate in PLAN §0)."""
    fsk4 = _spec(
        "4fsk",
        16,
        15.0,
        inner=CONV,
        offset=-120_000.0 / SAMPLE_RATE,
        stream_offset=11,
        text="SANKET 4FSK FRAME ",
    )
    scene = Scene(samples=1 << 19, signals=(fsk4,), noise_db=NOISE_DB, sample_rate=SAMPLE_RATE)
    g = generate(scene, SEED + 11)
    return g, scene, [_frames_truth(g, 0, "4FSK", "4fsk", -120_000.0)]


RAW_RATE = 1_000_000.0
WAV_RATE = 48_000


def build_raw() -> tuple[Generated, Scene, list[TruthEntry]]:
    """One coded QPSK signal for a headerless raw file: no sample rate anywhere (the scene's
    rate is None, the name has no rate hint). 1 MS/s is the rate it was generated at."""
    qpsk = _spec(
        "qpsk",
        10,
        15.0,
        inner=CONV,
        offset=150_000.0 / RAW_RATE,
        stream_offset=19,
        text="SANKET RAW CF32 FRAME ",
    )
    scene = Scene(samples=1 << 18, signals=(qpsk,), noise_db=NOISE_DB)
    g = generate(scene, SEED + 12)
    truth = _frames_truth(g, 0, "QPSK", "qpsk (raw cf32, rate 1 MS/s once entered)", 150_000.0)
    return g, scene, [truth]


def build_wav() -> tuple[Generated, Scene, list[TruthEntry]]:
    """A narrow coded QPSK signal in a 48 kHz stereo IQ WAV (I left, Q right): 4 kBd, so the
    rate in the WAV header is the one that matters."""
    qpsk = _spec(
        "qpsk",
        12,
        15.0,
        inner=CONV,
        offset=6_000.0 / WAV_RATE,
        stream_offset=23,
        text="SANKET WAV IQ FRAME ",
    )
    scene = Scene(samples=8 * WAV_RATE, signals=(qpsk,), noise_db=NOISE_DB, sample_rate=WAV_RATE)
    g = generate(scene, SEED + 13)
    return g, scene, [_frames_truth(g, 0, "QPSK", "qpsk (48 kHz stereo WAV)", 6_000.0)]


def write_raw(stem: Path, g: Generated) -> Path:
    """Headerless complex float32, little endian: `<stem>.cf32` and nothing else about it."""
    path = stem.with_suffix(".cf32")
    path.write_bytes(g.samples.astype("<c8").tobytes())
    return path


def write_wav(stem: Path, g: Generated, rate: int, level_dbfs: float = -12.0) -> Path:
    """16-bit stereo PCM WAV, I = left and Q = right, at `level_dbfs` RMS."""
    rms = math.sqrt(float(np.mean(np.abs(g.samples) ** 2)) / 2)
    scaled = g.samples / rms * 10 ** (level_dbfs / 20)
    pcm = np.empty(2 * len(scaled), "<i2")
    pcm[0::2] = np.clip(np.round(scaled.real * 32768), -32768, 32767)
    pcm[1::2] = np.clip(np.round(scaled.imag * 32768), -32768, 32767)
    path = stem.with_suffix(".wav")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return path


def write_and_verify(stem: Path, g: Generated, scene: Scene, truth: list[TruthEntry]) -> bool:
    stem.parent.mkdir(parents=True, exist_ok=True)
    path = write_sigmf(stem, g, scene, "cf32_le")
    print(f"\nwrote {path} and {path.with_suffix('.sigmf-data')}")
    _write_truth(stem, truth)
    assert scene.sample_rate is not None
    return _verify(path, truth, scene.sample_rate)


def _write_truth(stem: Path, truth: list[TruthEntry]) -> None:
    truth_path = stem.with_suffix(".truth.json")
    truth_path.write_text(json.dumps(truth, indent=2), encoding="utf-8")
    print(f"wrote {truth_path}")
    for t in truth:
        n_frames = len(t.get("expectPayloadHex") or [])
        extra = f", {n_frames} truth frames" if n_frames else ""
        print(f"  {t['label']:8s} @ {t['offsetHz']:+.0f} Hz  {t['kind']:8s}{extra}")


def _verify(path: Path, truth: list[TruthEntry], sample_rate: float | None = None) -> bool:
    """Open, detect and analyse every detection as the backend does. With no `sample_rate` it
    must be the file's own, MEASURED (a WAV header, say)."""
    print("verifying: open -> detect -> analyse (as the backend does)")
    (opened,) = open_path(path)
    if sample_rate is None:
        rate = opened.recording.assumptions.sample_rate
        if rate.level is not EvidenceLevel.MEASURED or not isinstance(rate.value, float | int):
            print(f"  FAIL: the file's sample rate is {rate.level.value}, not MEASURED")
            return False
        sample_rate = float(rate.value)
        print(f"  sample rate {sample_rate:g} Hz is MEASURED ({rate.method})")
    return _check_detections(opened, truth, sample_rate)


def _verify_raw(path: Path, truth: list[TruthEntry], rate: float) -> bool:
    """The headerless file through the backend: it must open with the sample rate UNKNOWN (and
    ask for it), and entering `rate` must analyse the signal to VERIFIED, every passing frame
    matching the transmitted payload."""
    print("verifying: open through the backend -> sample rate UNKNOWN -> enter it -> analyse")
    with tempfile.TemporaryDirectory() as tmp:
        dist = Path(tmp) / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<!doctype html><title>Sanket</title>")
        with TestClient(create_app(dist, Path(tmp) / "workspace")) as client:
            opened = client.post("/api/v1/recordings", json={"path": str(path)}).json()
            stated = opened["assumptions"]["sampleRate"]
            print(f"  opened: sample rate {stated['level']}, sampleRate={opened['sampleRate']}")
            if opened["sampleRate"] is not None or stated["level"] != "UNKNOWN":
                print("  FAIL: a headerless file must open with the sample rate UNKNOWN")
                return False
            entered = client.put(
                f"/api/v1/recordings/{opened['id']}/assumptions", json={"sampleRate": rate}
            ).json()
            with client.stream("GET", f"/api/v1/recordings/{opened['id']}/events") as stream:
                for _ in stream.iter_lines():
                    pass  # until the analysis ends
            done = client.get(f"/api/v1/recordings/{opened['id']}").json()
            for _ in range(100):  # the finished analysis is kept just after the stream ends
                if client.get("/api/v1/history").json():
                    break
                time.sleep(0.1)
            print(
                f"  entered {rate:g} Hz: {entered['assumptions']['sampleRate']['level']}; "
                f"{len(done['detections'])} detection(s)"
            )
            if len(done["detections"]) != len(truth):
                print(f"  FAIL: expected {len(truth)} detections")
                return False
            ok = True
            for i, t in enumerate(truth):
                table = client.get(
                    f"/api/v1/recordings/{opened['id']}/detections/{i}/frames"
                ).json()
                passing = [f["payloadHex"] for f in table["frames"] if f["crc"] == "pass"]
                level = done["detections"][i]["analysis"]["level"]
                expect = t.get("expectPayloadHex") or []
                good = bool(passing) and level == "VERIFIED" and all(h in expect for h in passing)
                print(
                    f"  detection {i}: level={level} passing={len(passing)} -> "
                    f"{'OK' if good else 'FAIL'}"
                )
                ok = ok and good
            return ok


def _check_detections(opened: Any, truth: list[TruthEntry], sample_rate: float) -> bool:
    with opened.recording.reader() as reader:
        detections = detect(reader, real=False).detections
    print(f"{len(detections)} detection(s)")
    if len(detections) != len(truth):
        print(f"  FAIL: expected {len(truth)} detections, got {len(detections)}")
        return False
    ok = True
    for i, d in enumerate(detections):
        with opened.recording.reader() as reader:
            report = analyse(reader, d, sample_rate=sample_rate)
        centre_hz = (d.low + d.high) / 2 * sample_rate
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
            elif report.level is not EvidenceLevel.VERIFIED:
                print(f"    FAIL: {nearest['label']} is {report.level.value}, not VERIFIED")
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


def _without_scene(
    built: tuple[Generated, Scene, list[TruthEntry]],
) -> tuple[Generated, list[TruthEntry]]:
    return built[0], built[2]


def write_and_verify_raw(stem: Path, g: Generated, truth: list[TruthEntry]) -> bool:
    stem.parent.mkdir(parents=True, exist_ok=True)
    path = write_raw(stem, g)
    print(f"\nwrote {path} (headerless: no sample rate in the file or its name)")
    _write_truth(stem, truth)
    return _verify_raw(path, truth, RAW_RATE)


def write_and_verify_wav(stem: Path, g: Generated, truth: list[TruthEntry]) -> bool:
    stem.parent.mkdir(parents=True, exist_ok=True)
    path = write_wav(stem, g, WAV_RATE)
    print(f"\nwrote {path} (16-bit stereo, I left and Q right, {WAV_RATE} Hz in the header)")
    _write_truth(stem, truth)
    return _verify(path, truth)


def _systems_check() -> bool:
    """The known-system sample (tools/demo_systems.py): written and verified here so one run makes
    and checks every bundled recording."""
    from demo_systems import build_systems, verify_systems, write

    stem = OUT_DIR / "scene_systems"
    g, scene, truth = build_systems()
    write(stem, g, scene, truth)
    return verify_systems(stem, g, scene, truth)


def main() -> None:
    print(f"seed={SEED} sample_rate={SAMPLE_RATE:g} samples={SAMPLES}")
    results = {
        "scene": write_and_verify(OUT_DIR / "scene", *build_main()),
        "scene_widen": write_and_verify(OUT_DIR / "scene_widen", *build_widen()),
        "scene_fsk": write_and_verify(OUT_DIR / "scene_fsk", *build_fsk()),
        "scene_ldpc": write_and_verify(OUT_DIR / "scene_ldpc", *build_ldpc()),
        "scene_coverage": write_and_verify(OUT_DIR / "scene_coverage", *build_coverage()),
        "scene_fsk4": write_and_verify(OUT_DIR / "scene_fsk4", *build_fsk4()),
        "scene_raw": write_and_verify_raw(OUT_DIR / "scene_raw", *_without_scene(build_raw())),
        "scene_wav": write_and_verify_wav(OUT_DIR / "scene_wav", *_without_scene(build_wav())),
        "scene_systems": _systems_check(),
    }
    failed = [name for name, ok in results.items() if not ok]
    if failed:
        print(f"\nSOME CHECKS FAILED ({', '.join(failed)}) - see above")
        sys.exit(1)
    print("\nall checks passed")


if __name__ == "__main__":
    main()
