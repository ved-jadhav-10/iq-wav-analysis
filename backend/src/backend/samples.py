"""The sample recordings that ship with Sanket, so a first-time user can try it with no file.

They are the synthetic scenes `tools/make_demo.py` writes (dsp.synth, exact truth known), always
labelled synthetic. In a frozen build they sit in `samples/` beside the program; from a source
tree they are `data/demo/`. A sample is listed only when its recording is there: a `.sigmf-meta`
(with its `.sigmf-data`), else a headerless `.cf32` or a `.wav`.
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
        "scene_coverage",
        "Helical, Forney and blind-identified codes",
        "16QAM through a helical interleaver, QPSK through a convolutional (Forney) interleaver, "
        "and QPSK under a K=9 convolutional code that is not in any catalogue, found blind. "
        "Frames carry readable text.",
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
        "scene_fsk4",
        "A single 4-FSK signal",
        "One coded 4-FSK transmission: four tones, two bits per symbol, decoded to frames "
        "with readable text.",
    ),
    (
        "scene_ldpc",
        "LDPC-coded signal (Wi-Fi 802.11n code)",
        "A QPSK signal protected by a standard LDPC code, identified from a catalogue of "
        "published codes and proved by its frame CRC.",
    ),
    (
        "scene_systems",
        "Known systems: POCSAG, NAVTEX and AIS",
        "Three public systems in one recording, each recognised blind and proved by its own "
        "check (BCH, four-of-seven repetition, CRC-16): the paging messages and the NAVTEX "
        "warning are shown as text.",
    ),
    (
        "scene_wav",
        "A stereo WAV recording",
        "A narrow coded QPSK signal in a 48 kHz stereo WAV (I left, Q right): the sample rate "
        "comes from the WAV header and the frames are proved by CRC.",
    ),
    (
        "scene_raw",
        "A raw file with no sample rate",
        "A headerless complex-float file that states no sample rate. Sanket says the rate is "
        "unknown and asks for it; enter 1 MS/s and the coded QPSK signal decodes and is proved "
        "by CRC.",
    ),
)

# What a sample's recording can be, in the order they are looked for, and the files that go
# with each (the SigMF data file, or nothing).
RECORDING_SUFFIXES: tuple[tuple[str, str | None], ...] = (
    (".sigmf-meta", ".sigmf-data"),
    (".cf32", None),
    (".wav", None),
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


def _recording(folder: Path, sample_id: str) -> tuple[Path, int] | None:
    """The file to open for `sample_id` and the bytes of everything that goes with it."""
    for suffix, companion in RECORDING_SUFFIXES:
        path = folder / f"{sample_id}{suffix}"
        if not path.is_file():
            continue
        size = path.stat().st_size
        if companion is not None:
            data = folder / f"{sample_id}{companion}"
            size += data.stat().st_size if data.is_file() else 0
        return path, size
    return None


def list_samples(folder: Path | None = None) -> tuple[Sample, ...]:
    folder = folder or samples_dir()
    found: list[Sample] = []
    for sample_id, title, description in CATALOGUE:
        recording = _recording(folder, sample_id)
        if recording is None:
            continue
        path, size = recording
        found.append(Sample(sample_id, title, description, path, _signals(folder, sample_id), size))
    return tuple(found)


def find(sample_id: str, folder: Path | None = None) -> Sample | None:
    return next((s for s in list_samples(folder) if s.id == sample_id), None)
