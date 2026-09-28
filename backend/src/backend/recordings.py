"""Opening a local recording and building its tile pyramid, kept in memory for this server
process's lifetime (PLAN §5 M2). This is deliberately narrower than the full job/workspace
store PLAN §3 describes (SQLite, content-addressed artifacts, job history): that is M7's scope.
Here, a recording is opened once, its pyramid built once, and both are held in a dict - nothing
is persisted across a restart, and there is no job runner. It exists so the frontend's waterfall
has real, server-computed tiles to switch to instead of the demo texture (PLAN's M2 exit gate),
without building ahead of that milestone's own scope.
"""

import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from dsp.ingest.dispatch import NeedsDecompression, open_path
from dsp.results import Assumptions
from dsp.tiles import Pyramid, build_pyramid


class RecordingError(ValueError):
    """A recording can't be opened or its format is not yet known well enough to tile it."""


@dataclass(frozen=True)
class Recording:
    id: str
    path: Path
    container: str
    name: str
    assumptions: Assumptions
    num_samples: int
    real: bool
    pyramid: Pyramid


class RecordingStore:
    """Recordings opened this server run, by id. Not thread-per-request safe beyond the lock
    around registration; reads of an already-built `Recording` are safe (it's immutable)."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._recordings: dict[str, Recording] = {}

    def open(self, path: Path) -> Recording:
        if not path.is_file():
            raise RecordingError(f"{path} is not a file")
        try:
            found = open_path(path)
        except NeedsDecompression as exc:
            raise RecordingError(str(exc)) from exc
        except ValueError as exc:
            raise RecordingError(f"could not read {path.name}: {exc}") from exc
        if len(found) != 1:
            raise RecordingError(
                f"{path.name} holds {len(found)} recordings; opening a multi-capture archive "
                "isn't supported yet, pick a single-capture file"
            )
        opened = found[0]
        fmt = opened.recording.sample_format
        if fmt is None:
            raise RecordingError(
                f"{path.name}'s sample format is unknown; resolve it before tiling "
                "(see the recording's Assumptions block)"
            )
        real = not fmt.is_complex
        with opened.recording.reader() as reader:
            pyramid = build_pyramid(reader, real=real)
        recording = Recording(
            id=str(uuid.uuid4()),
            path=path,
            container=opened.container,
            name=opened.name,
            assumptions=opened.recording.assumptions,
            num_samples=pyramid.samples,
            real=real,
            pyramid=pyramid,
        )
        with self._lock:
            self._recordings[recording.id] = recording
        return recording

    def get(self, recording_id: str) -> Recording | None:
        return self._recordings.get(recording_id)
