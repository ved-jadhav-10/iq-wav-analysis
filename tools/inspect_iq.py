"""Quick report on any recording: the reader that opens it, its Assumptions block, what is still
UNKNOWN or listed for review, and sample statistics. A dev-time tool for the `inspect-iq` skill.

    uv run python tools/inspect_iq.py <file> [<file> ...]

The reader is picked from the extension and the header magic here, as a stand-in until the
product has a dispatcher (M2). Compressed `.gz`/`.zip` files are only sized, never unpacked.
Statistics read at most STATS_SAMPLES samples from the start, so large files stay cheap.
"""

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from dsp.evidence import Parameter
from dsp.ingest.archives import ArchiveError, unpacked_size
from dsp.ingest.audio import read_audio
from dsp.ingest.blue import read_blue
from dsp.ingest.npy import read_npy
from dsp.ingest.raw import RawRecording, read_raw
from dsp.ingest.reader import SampleReader
from dsp.ingest.sdriq import read_sdriq
from dsp.ingest.sigmf import read_sigmf, read_sigmf_archive
from dsp.ingest.vita49 import read_vita49
from dsp.ingest.wav import read_wav
from dsp.results import NO_FILES, Assumptions, Results

STATS_SAMPLES = 1 << 20
AUDIO = {".flac", ".mp3", ".ogg", ".oga"}
VITA = {".vrt", ".vrl", ".vita49", ".v49"}


def open_recordings(path: Path) -> list[tuple[str, Any]]:
    """(reader name, recording) for each recording in the file."""
    name = path.name.lower()
    with path.open("rb") as file:
        head = file.read(12)
    if name.endswith(".sigmf-meta"):
        return [("SigMF", read_sigmf(path))]
    if name.endswith(".sigmf-data") and path.with_suffix(".sigmf-meta").exists():
        return [("SigMF", read_sigmf(path.with_suffix(".sigmf-meta")))]
    if name.endswith(".sigmf"):
        return [("SigMF archive", r) for r in read_sigmf_archive(path)]
    if head[:4] in (b"RIFF", b"RIFX", b"RF64", b"BW64") or name.endswith(".w64"):
        return [("WAV", read_wav(path))]
    if head[:6] == b"\x93NUMPY":
        return [("NumPy .npy", read_npy(path))]
    if head[:4] == b"BLUE":
        return [("MIDAS Blue", read_blue(path))]
    if name.endswith(".sdriq"):
        return [("SDRangel .sdriq", read_sdriq(path))]
    if path.suffix.lower() in VITA:
        return [("VITA 49", read_vita49(path))]
    if path.suffix.lower() in AUDIO:
        return [("compressed audio", read_audio(path))]
    return [("raw (format sniffer)", read_raw(path))]


def _value(p: Parameter) -> str:
    value = "none" if p.value is None else f"{p.value}{' ' + p.unit if p.unit else ''}"
    alts = ", ".join(str(a.value) for a in p.alternatives[:4])
    return value + (f" (candidates: {alts})" if p.value is None and alts else "")


def _stats(recording: Any) -> list[str]:
    if recording.sample_format is None:
        return ["Sample statistics: not computed, the sample format is UNKNOWN."]
    # A raw file's samples start at byte 0 on the sniffer's stated convention.
    opened = (
        SampleReader(recording.data_path, recording.sample_format)
        if isinstance(recording, RawRecording)
        else recording.reader()
    )
    with opened as reader:
        n = min(reader.num_samples, STATS_SAMPLES)
        x = np.asarray(reader.read(0, n))
    if n == 0:
        return ["Sample statistics: the recording holds no samples."]
    comps = np.concatenate([np.real(x), np.imag(x)]) if np.iscomplexobj(x) else x
    full = float(np.mean(np.abs(comps) >= 0.999))
    lines = [
        f"Sample statistics over the first {n:,} samples:",
        f"- RMS {10 * np.log10(np.mean(np.abs(x) ** 2) + 1e-30):.1f} dB full scale; "
        f"{100 * full:.3f} % of components at full scale (clipping)",
        f"- DC {np.mean(x):.4g}",
    ]
    if np.iscomplexobj(x):
        pi, pq = np.mean(np.real(x) ** 2), np.mean(np.imag(x) ** 2)
        lines.append(f"- I/Q power ratio {10 * np.log10((pi + 1e-30) / (pq + 1e-30)):+.2f} dB")
    return lines


def report(path: Path) -> str:
    out = [f"# {path.name}", ""]
    if path.suffix.lower() in (".gz", ".zip"):
        try:
            size = unpacked_size(path)
        except ArchiveError as error:
            return "\n".join([*out, f"Not readable: {error}", ""])
        exact = "" if size.exact else " at least"
        return "\n".join(
            [*out, f"Compressed: unpacks to{exact} {size.bytes:,} bytes. Decompress it first.", ""]
        )
    try:
        recordings = open_recordings(path)
    except (ValueError, OSError) as error:
        return "\n".join([*out, f"Not readable: {error}", ""])
    for reader_name, rec in recordings:
        a: Assumptions = rec.assumptions
        review = Results(
            sanket_version="0.1.0", recording=NO_FILES, catalogues=(), assumptions=a, stages=()
        ).needs_review
        out += [f"Reader: {reader_name}", "", "| Assumption | Value | Level | Method |"]
        out.append("|---|---|---|---|")
        out += [f"| {p.name} | {_value(p)} | {p.level} | {p.method} |" for p in a.parameters()]
        out.append("")
        unknown = [p.name for p in a.parameters() if p.value is None]
        out.append(f"UNKNOWN: {', '.join(unknown) if unknown else 'nothing'}")
        out.append(f"Needs review: {', '.join(r.parameter for r in review) or 'nothing'}")
        for p in a.parameters():
            out += [f"- warning ({p.name}): {w}" for w in p.warnings]
        quadrature = getattr(rec, "quadrature", None)
        if quadrature is not None:
            out.append(f"Stereo quadrature check: {quadrature.verdict}")
        out += ["", *_stats(rec), ""]
    return "\n".join(out)


def main(argv: Sequence[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    for arg in argv:
        print(report(Path(arg)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
