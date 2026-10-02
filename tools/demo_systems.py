"""The known-system sample: one recording carrying public systems that Sanket recognises blind.

`build_systems()` is one scene at 48 kS/s with a POCSAG paging transmission (2-FSK, 1200 Bd),
a NAVTEX / SITOR-B broadcast (2-FSK, 100 Bd) and an AIS burst (GMSK, 9600 Bd), each at its own
offset and in its own stretch of time. Every one must reach VERIFIED through the Match stage,
by that system's own check (BCH re-encode, four-of-seven repetition, CRC-16/X.25), and the text it
carries must be read back exactly. The text is shown but never used as evidence.

The sample rate is 48 kS/s, not 1 MS/s as the other samples use: a NAVTEX message needs about
ten seconds at 100 Bd, which is half a million samples at 48 kS/s and ten million at 1 MS/s.

All synthetic (dsp.synth); the transmissions are generated from the public specifications
independently of the decoder. `verify_systems` writes nothing: it opens the recording that
`make_demo.write_and_verify`'s writer produced and checks it the way the backend reads it.

Run on its own: uv run python tools/demo_systems.py  (writes data/demo/scene_systems)
"""

import json
import math
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from dsp.analyse import analyse
from dsp.detect import detect
from dsp.evidence import EvidenceLevel
from dsp.ingest.dispatch import open_path
from dsp.synth.chain import Generated, Scene, SignalSpec, generate, write_sigmf
from dsp.synth.systems import Ais, Navtex, Pocsag

if TYPE_CHECKING:
    from make_demo import TruthEntry

SEED = 90210 + 20
NOISE_DB = -20.0
SAMPLE_RATE = 48_000.0
SAMPLES = 14 * 48_000
OUT_DIR = Path("data/demo")

PAGES = (
    (1234567, 3, "SANKET DEMO PAGE ONE"),
    (42, 3, "NTRO SIH26147 ALL OK"),
    (2042071, 3, "STAND BY ON CHANNEL SIXTEEN"),
)
NAVTEX = Navtex(
    station="E",
    subject="A",
    serial=12,
    text="GALE WARNING ARABIAN SEA FORCE 8",
)
AIS = Ais()


def _power(esn0_db: float, sps: float) -> float:
    """Es/N0 = SNR + 10 log10(sps), so the per-sample power follows from the target Es/N0."""
    return NOISE_DB + esn0_db - 10 * math.log10(sps)


def _hz(hz: float) -> float:
    return hz / SAMPLE_RATE


def build_systems() -> "tuple[Generated, Scene, list[TruthEntry]]":
    pocsag = SignalSpec(
        modulation="2fsk",
        sps=SAMPLE_RATE / 1200.0,
        fsk_index=1.0,
        power_db=_power(15.0, SAMPLE_RATE / 1200.0),
        frame=None,
        system=Pocsag(pages=PAGES),
        offset=_hz(-15_300.0),
        start=3_000,
        duration=150_000,
    )
    navtex = SignalSpec(
        modulation="2fsk",
        sps=SAMPLE_RATE / 100.0,
        fsk_index=1.0,
        power_db=_power(15.0, SAMPLE_RATE / 100.0),
        frame=None,
        system=NAVTEX,
        offset=_hz(9_700.0),
        start=20_000,
        duration=640_000,
    )
    ais = SignalSpec(
        modulation="2fsk",
        sps=SAMPLE_RATE / 9600.0,
        fsk_index=0.5,
        fsk_bt=0.4,
        power_db=_power(22.0, SAMPLE_RATE / 9600.0),
        frame=None,
        system=AIS,
        offset=_hz(-2_100.0),
        start=60_000,
        duration=90_000,
    )
    scene = Scene(
        samples=SAMPLES,
        signals=(pocsag, navtex, ais),
        noise_db=NOISE_DB,
        sample_rate=SAMPLE_RATE,
    )
    g = generate(scene, SEED)
    truth: list[TruthEntry] = [
        {
            "label": "POCSAG",
            "modulation": "2fsk, 1200 Bd",
            "kind": "fsk",
            "offsetHz": -15_300.0,
            "expectedLevel": "VERIFIED",
            "reason": "known system: BCH(31,21) + parity re-encode, sync word every batch; pages: "
            + " | ".join(t for _, _, t in PAGES),
        },
        {
            "label": "NAVTEX",
            "modulation": "2fsk, 100 Bd",
            "kind": "fsk",
            "offsetHz": 9_700.0,
            "expectedLevel": "VERIFIED",
            "reason": f"known system: four-of-seven characters repeated five slots later; "
            f"message {NAVTEX.station}{NAVTEX.subject}{NAVTEX.serial:02d}: {NAVTEX.text}",
        },
        {
            "label": "AIS",
            "modulation": "gmsk, 9600 Bd",
            "kind": "fsk",
            "offsetHz": -2_100.0,
            "expectedLevel": "VERIFIED",
            "reason": "known system: HDLC frames pass CRC-16/X.25; MMSIs "
            + ", ".join(str(m) for m in AIS.mmsis),
        },
    ]
    return g, scene, truth


def _expected_lines(label: str) -> list[str]:
    if label == "POCSAG":
        return [f'"{text}"' for _, _, text in PAGES]
    if label == "NAVTEX":
        return [f"{NAVTEX.station}{NAVTEX.subject}{NAVTEX.serial:02d}: {NAVTEX.text}"]
    return [f"MMSI {m:09d}" for m in AIS.mmsis]


_SYSTEM_NAME = {"POCSAG": "POCSAG paging", "NAVTEX": "NAVTEX (SITOR-B)", "AIS": "AIS"}
_TEXT_ID = {"POCSAG": "pages", "NAVTEX": "messages", "AIS": "ais_messages"}


def _say(text: str) -> None:
    """print, safe on a console that cannot show the headline's arrow."""
    print(text.encode("ascii", "replace").decode("ascii"))


def verify_systems(stem: Path, g: Generated, scene: Scene, truth: "list[TruthEntry]") -> bool:
    """Open the recording written at `stem` (`write_sigmf` + a .truth.json, as
    `make_demo.write_and_verify` writes them), detect, analyse every detection, and check that
    each system reached VERIFIED through Match with its exact text, and that nothing else did."""
    path = stem.with_suffix(".sigmf-meta")
    (opened,) = open_path(path)
    with opened.recording.reader() as reader:
        detections = detect(reader, real=False).detections
    print(f"{len(detections)} detection(s)")
    ok = True
    if len(detections) != len(truth):
        print(f"  FAIL: expected {len(truth)} detections, got {len(detections)}")
        ok = False
    seen: set[str] = set()
    for i, d in enumerate(detections):
        with opened.recording.reader() as reader:
            report = analyse(reader, d, sample_rate=SAMPLE_RATE)
        centre_hz = (d.low + d.high) / 2 * SAMPLE_RATE
        nearest = min(truth, key=lambda t: abs(t["offsetHz"] - centre_hz))
        label = nearest["label"]
        match_stage = next((s for s in report.stages if s.id == "match"), None)
        system = (
            next((p for p in match_stage.parameters if p.id == "system"), None)
            if match_stage
            else None
        )
        value = None if system is None else system.value
        print(
            f"  detection {i}: centre {centre_hz:+.0f} Hz (nearest truth: {label}) "
            f"level={report.level.value} system={value!r}"
        )
        if label in seen:
            print(f"    FAIL: a second detection near {label}")
            ok = False
        seen.add(label)
        if (
            system is None
            or system.level is not EvidenceLevel.VERIFIED
            or value != _SYSTEM_NAME[label]
        ):
            print(f"    FAIL: expected {_SYSTEM_NAME[label]} VERIFIED through Match")
            ok = False
            continue
        if report.level is not EvidenceLevel.VERIFIED or _SYSTEM_NAME[label] not in report.headline:
            _say(f"    FAIL: headline {report.headline!r} at level {report.level.value}")
            ok = False
        assert match_stage is not None
        text = next((p for p in match_stage.parameters if p.id == _TEXT_ID[label]), None)
        shown = [] if text is None else list(text.evidence)
        for line in shown:
            _say(f"      {line}")
        missing = [e for e in _expected_lines(label) if not any(e in s for s in shown)]
        if missing:
            print(f"    FAIL: not read back: {missing}")
            ok = False
        else:
            print(f"    OK: {label} VERIFIED, text read back exactly")
    if seen != {t["label"] for t in truth}:
        print(f"  FAIL: systems found {sorted(seen)}")
        ok = False
    return ok


def write(stem: Path, g: Generated, scene: Scene, truth: "list[TruthEntry]") -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    write_sigmf(stem, g, scene, "cf32_le")
    stem.with_suffix(".truth.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")


def main() -> None:
    g, scene, truth = build_systems()
    stem = OUT_DIR / "scene_systems"
    write(stem, g, scene, truth)
    sys.exit(0 if verify_systems(stem, g, scene, truth) else 1)


if __name__ == "__main__":
    main()
