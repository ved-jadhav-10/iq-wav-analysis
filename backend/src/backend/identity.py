"""What a recording is, by content: the files its samples and metadata come from, hashed.

A results document carries this so any export traces to the exact bytes analysed (PLAN §2,
"Reproducibility"). Files are hashed in chunks, never loaded whole, and by name only: a path
would leak the user's directory layout into a document that gets shared.
"""

import hashlib
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

from dsp.ingest.reader import Segment
from dsp.results import FileIdentity, RecordingIdentity

CHUNK = 8 << 20


@lru_cache(maxsize=64)
def _sha256(path: Path, size: int, mtime_ns: int) -> str:
    """The digest of one file; the size and modification time key the cache, so a file that
    changed is hashed again."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while block := file.read(CHUNK):
            digest.update(block)
    return digest.hexdigest()


def file_identity(path: Path) -> FileIdentity:
    stat = path.stat()
    return FileIdentity(
        name=path.name,
        size_bytes=stat.st_size,
        sha256=_sha256(path, stat.st_size, stat.st_mtime_ns),
    )


def source_files(paths: Iterable[Path], recording: Any) -> tuple[Path, ...]:
    """The named files plus the dataset the recording reads its samples from (a SigMF
    metadata file names its data file; a numbered sequence is its own list), without repeats,
    sorted by name."""
    found = set(paths)
    data = getattr(recording, "data_path", None)
    if isinstance(data, Path):
        found.add(data)
    segments = getattr(recording, "segments", None)
    if isinstance(segments, tuple):
        found |= {s.path for s in segments if isinstance(s, Segment)}  # type: ignore[reportUnknownVariableType]
    return tuple(sorted((p for p in found if p.is_file()), key=lambda p: (p.name, str(p))))


def recording_identity(
    container: str, samples: int, paths: Iterable[Path], recording: Any
) -> RecordingIdentity:
    files = tuple(file_identity(p) for p in source_files(paths, recording))
    return RecordingIdentity(container=container, samples=samples, files=files)
