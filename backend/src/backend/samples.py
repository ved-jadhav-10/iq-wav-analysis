"""The sample recordings that ship with Sanket, so a first-time user can try it with no file.

They are the synthetic scenes `tools/make_demo.py` writes (dsp.synth, exact truth known), always
labelled synthetic. In a frozen build they sit in `samples/` beside the program; from a source
tree they are `data/demo/`. A sample is listed only when its `.sigmf-meta` is there.
"""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Sample:
    id: str
    title: str
    description: str
    path: Path
    signals: int
    size_bytes: int


# (id, title, what it shows) in the order a visitor should try them.
CATALOGUE: tuple[tuple[str, str, str], ...] = (
    (
        "scene",
        "Four signals in one band",
        "Two coded digital signals that Sanket decodes and proves with a CRC, one noisy signal "
        "it honestly refuses to decode, and an FM broadcast it labels as analog.",
    ),
    (
        "scene_widen",
        "Interleaved and Reed-Solomon coded",
        "An 8PSK signal through a block interleaver and a QPSK signal inside a Reed-Solomon "
        "outer code: layers Sanket peels off one at a time.",
    ),
    (
        "scene_fsk",
        "A single FSK signal",
        "One coded 2-FSK transmission: shows tone-based demodulation and the symbol-rate estimate.",
    ),
    (
        "scene_ldpc",
        "LDPC-coded signal (Wi-Fi 802.11n code)",
        "A QPSK signal protected by a standard LDPC code, identified from a catalogue of "
        "published codes and proved by its frame CRC.",
    ),
)


def samples_dir() -> Path:
    if override := os.environ.get("SANKET_SAMPLES"):
        return Path(override)
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "samples"
    return REPO_ROOT / "data" / "demo"


def _signals(folder: Path, stem: str) -> int:
    try:
        return len(json.loads((folder / f"{stem}.truth.json").read_text("utf-8")))
    except (OSError, ValueError):
        return 0


def list_samples(folder: Path | None = None) -> tuple[Sample, ...]:
    folder = folder or samples_dir()
    found: list[Sample] = []
    for sample_id, title, description in CATALOGUE:
        meta = folder / f"{sample_id}.sigmf-meta"
        if not meta.is_file():
            continue
        data = folder / f"{sample_id}.sigmf-data"
        size = meta.stat().st_size + (data.stat().st_size if data.is_file() else 0)
        found.append(Sample(sample_id, title, description, meta, _signals(folder, sample_id), size))
    return tuple(found)


def find(sample_id: str, folder: Path | None = None) -> Sample | None:
    return next((s for s in list_samples(folder) if s.id == sample_id), None)
