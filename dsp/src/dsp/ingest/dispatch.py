"""Pick the reader for a file from its header magic and name (PLAN §3, Inputs).

Header magic decides first (RIFF/RF64/Wave64, NumPy, MIDAS Blue); then names that carry their
format with them (SigMF, `.sdriq`, VITA 49 extensions, compressed audio); anything else is read
as raw bytes through the format sniffer, which states every layout fact it assumes. A `.gz` or
`.zip` file is refused with the reason: it must be decompressed into the workspace first
(`archives.decompress`), because analysis needs random access.

Every reader returns a recording with the same surface: `assumptions`, `sample_format` and a
chunked `reader()`; the analysis never needs to know which container it came from.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from dsp.ingest.audio import AudioRecording, read_audio
from dsp.ingest.blue import read_blue
from dsp.ingest.formats import SampleFormat
from dsp.ingest.npy import read_npy
from dsp.ingest.raw import RawRecording, read_raw
from dsp.ingest.sdriq import read_sdriq
from dsp.ingest.sigmf import read_sigmf, read_sigmf_archive
from dsp.ingest.vita49 import read_vita49
from dsp.ingest.wav import read_wav
from dsp.results import Assumptions

AUDIO = frozenset({".flac", ".mp3", ".ogg", ".oga"})
VITA = frozenset({".vrt", ".vrl", ".vita49", ".v49"})
COMPRESSED = frozenset({".gz", ".zip"})


class SampleSource(Protocol):
    """The chunked sample interface every reader offers."""

    num_samples: int

    def read(self, start: int, count: int) -> Any: ...

    def chunks(self, size: int = ...) -> Iterator[Any]: ...

    def close(self) -> None: ...


class AnyRecording(Protocol):
    @property
    def sample_format(self) -> SampleFormat | None: ...

    @property
    def assumptions(self) -> Assumptions: ...

    def reader(self, *, swap_iq: bool = False) -> Any: ...


@dataclass(frozen=True)
class Opened:
    """One recording found in a file, with the name of the reader that opened it."""

    container: str
    name: str
    recording: AnyRecording

    @property
    def lossy(self) -> bool:
        """Decoded from a lossy codec: digital labels are capped at HYPOTHESIS."""
        return isinstance(self.recording, AudioRecording) and self.recording.lossy

    @property
    def real_or_complex_tie(self) -> str | None:
        """For a raw file whose real and complex readings the sniffer couldn't tell apart, the
        other reading's datatype; the analysis carries both forward (PLAN M2)."""
        rec = self.recording
        if not isinstance(rec, RawRecording):
            return None
        param = rec.datatype
        if param.convention is None or not isinstance(param.value, str):
            return None
        value = param.value
        return ("r" if value[0] == "c" else "c") + value[1:]

    @property
    def mono_audio(self) -> bool:
        """A real-valued recording: only positive frequencies carry information."""
        fmt = self.recording.sample_format
        return fmt is not None and not fmt.is_complex

    def reader_as(self, datatype: str) -> Any:
        """The samples read as another datatype (for a raw file's real/complex tie)."""
        rec = self.recording
        if not isinstance(rec, RawRecording):
            raise ValueError("only a raw file can be read as another datatype")
        return rec.reader(datatype=datatype)


class NeedsDecompression(ValueError):
    """The file is compressed; decompress it into the workspace before opening it."""


def open_path(path: Path) -> tuple[Opened, ...]:
    """Every recording in the file (a SigMF archive can hold several)."""
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix in COMPRESSED:
        raise NeedsDecompression(
            f"{path.name} is compressed. Analysis needs random access to the samples, so it is "
            "decompressed into the workspace first."
        )
    with path.open("rb") as file:
        head = file.read(40)
    if name.endswith(".sigmf-meta"):
        return (Opened("SigMF", path.name, read_sigmf(path)),)
    if name.endswith(".sigmf-data") and path.with_suffix(".sigmf-meta").exists():
        meta = path.with_suffix(".sigmf-meta")
        return (Opened("SigMF", meta.name, read_sigmf(meta)),)
    if name.endswith(".sigmf"):
        return tuple(Opened("SigMF archive", r.name, r) for r in read_sigmf_archive(path))
    if head[:4] in (b"RIFF", b"RIFX", b"RF64", b"BW64") or suffix == ".w64":
        return (Opened("WAV", path.name, read_wav(path)),)
    if head[:6] == b"\x93NUMPY":
        return (Opened("NumPy .npy", path.name, read_npy(path)),)
    if head[:4] == b"BLUE":
        return (Opened("MIDAS Blue", path.name, read_blue(path)),)
    if suffix == ".sdriq":
        return (Opened("SDRangel .sdriq", path.name, read_sdriq(path)),)
    if suffix in VITA:
        return (Opened("VITA 49", path.name, read_vita49(path)),)
    if suffix in AUDIO:
        return (Opened("Compressed audio", path.name, read_audio(path)),)
    return (Opened("Raw samples (format sniffer)", path.name, read_raw(path)),)
