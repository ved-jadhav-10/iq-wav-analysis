"""What a path can name: one recording file, a folder of them, or a numbered file sequence read
as one recording (PLAN §5 M7, "Every input route").

The server's open route and `sanket analyse` share this, so a folder or a sequence means the same
in both. Nothing is decided by guessing: a folder is a batch of its files, one recording each,
and files are joined into a sequence only when asked (`sequence=True`), because
`cap_1.cu8, cap_2.cu8` are as often two captures as two halves of one.
"""

from dataclasses import dataclass, replace
from pathlib import Path

from dsp.ingest.dispatch import NeedsDecompression, Opened, open_path
from dsp.ingest.formats import SampleFormat
from dsp.ingest.raw import RawRecording
from dsp.ingest.recording import Recording, entered
from dsp.ingest.sequence import numbered_sequence, read_sequence

# Files a folder holds beside its recordings; raw samples have no extension to go by, so anything
# not named here is offered as a recording and fails on its own if it isn't one.
NOT_RECORDINGS = frozenset(
    {".json", ".txt", ".md", ".csv", ".log", ".yaml", ".yml", ".html", ".pdf", ".png", ".jpg"}
)


class RecordingError(ValueError):
    """A path can't be opened as a recording, or its format isn't known well enough to tile it."""


class FormatUnknownError(RecordingError):
    """The sample format is UNKNOWN: the analyst picks one of `candidates` (or types another)."""

    def __init__(self, message: str, candidates: tuple[str, ...]) -> None:
        super().__init__(message)
        self.candidates = candidates


@dataclass(frozen=True)
class Input:
    """One recording's files: a single file, or a numbered sequence in number order."""

    paths: tuple[Path, ...]

    @property
    def name(self) -> str:
        first = self.paths[0].name
        return first if len(self.paths) == 1 else f"{first} (+{len(self.paths) - 1} files)"


def expand(path: Path, *, sequence: bool = False) -> tuple[Input, ...]:
    """The recordings `path` names: itself, or a folder's files in name order (not descending
    into subfolders). With `sequence`, numbered files that differ only in their number are
    joined into one recording each; a file with no numbered siblings stays alone."""
    if path.is_dir():
        files = _recordings_in(path)
        if not files:
            raise RecordingError(f"{path} holds no recordings")
    elif path.is_file():
        files = [path]
    else:
        raise RecordingError(f"{path} is not a file or a folder")
    if not sequence:
        return tuple(Input((f,)) for f in files)
    grouped: dict[tuple[Path, ...], Input] = {}
    for file in files:
        paths = (file,) if _is_sigmf(file) else numbered_sequence(file)
        grouped.setdefault(paths, Input(paths))
    return tuple(grouped.values())


def open_input(item: Input, datatype: str | None = None) -> Opened:
    """The one recording `item` holds, ready to read, or `RecordingError` saying why it isn't.

    `datatype` is the analyst's choice of sample format for a raw file or a sequence of raw
    files; it replaces the sniffer's and is recorded as entered. A container states its own
    format, so it takes none. A format still UNKNOWN raises `FormatUnknownError`."""
    opened = _open(item)
    if datatype is not None:
        opened = _with_datatype(opened, datatype)
    if opened.recording.sample_format is None:
        found = opened.recording.assumptions.datatype.alternatives
        raise FormatUnknownError(
            f"{opened.name}'s sample format is unknown; choose one",
            tuple(a.value for a in found if isinstance(a.value, str)),
        )
    return opened


def _with_datatype(opened: Opened, datatype: str) -> Opened:
    try:
        SampleFormat.parse(datatype)
    except ValueError as exc:
        raise RecordingError(f"{datatype!r} is not a sample format: {exc}") from exc
    source = opened.recording
    if isinstance(source, RawRecording):
        return replace(opened, recording=replace(source, entered_datatype=datatype))
    if isinstance(source, Recording) and opened.container == "Numbered sequence":
        # A WAV sequence states its format; a raw one carries the sniffer's guess.
        if not source.datatype.method.startswith("Format sniffer"):
            raise RecordingError(f"{opened.name} states its own sample format")
        return replace(
            opened,
            recording=replace(
                source, datatype=entered("datatype", datatype, prior=source.datatype)
            ),
        )
    raise RecordingError(f"{opened.container} files state their own sample format")


def _open(item: Input) -> Opened:
    path, *others = item.paths
    if others:
        try:
            recording = read_sequence(item.paths)
        except (ValueError, OSError) as exc:
            raise RecordingError(f"could not read {item.name} as one recording: {exc}") from exc
        return Opened("Numbered sequence", recording.name, recording)
    if not path.is_file():
        raise RecordingError(f"{path} is not a file")
    try:
        found = open_path(path)
    except NeedsDecompression as exc:
        raise RecordingError(str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise RecordingError(f"could not read {path.name}: {exc}") from exc
    if len(found) != 1:
        raise RecordingError(
            f"{path.name} holds {len(found)} recordings; opening a multi-capture archive "
            "isn't supported yet, pick a single-capture file"
        )
    (opened,) = found
    return opened


def _is_sigmf(path: Path) -> bool:
    return path.name.lower().endswith((".sigmf-meta", ".sigmf-data", ".sigmf"))


def _recordings_in(folder: Path) -> list[Path]:
    children = sorted(p for p in folder.iterdir() if p.is_file() and not p.name.startswith("."))
    return [
        p
        for p in children
        if p.suffix.lower() not in NOT_RECORDINGS
        # A SigMF pair is opened from its metadata, so its data file isn't a second recording.
        and not (p.name.lower().endswith(".sigmf-data") and p.with_suffix(".sigmf-meta").exists())
    ]
