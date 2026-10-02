"""SigMF out: the annotated metadata for a recording, and "Save as SigMF" for a raw file.

Both are built by `dsp.sigmf_out` from the results document. A SigMF recording's own metadata is
kept as it is and annotated; a raw file gets a Non-Conforming Dataset description next to it that
names the file, so the samples are never copied or touched. Other containers (WAV, archives,
sequences) are not described: their samples are not one raw dataset a SigMF reader could be
pointed at, and the functions say so rather than write something that would read wrong.
"""

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from dsp.ingest.raw import RawRecording
from dsp.results import Results
from dsp.sigmf_out import meta_for, render_meta

from .inputs import RecordingError


class NotDescribable(RecordingError):
    """This recording's container can't be written as SigMF metadata."""


def _meta_path(paths: Iterable[Path]) -> Path | None:
    return next((p for p in paths if p.name.lower().endswith(".sigmf-meta")), None)


def annotated_meta(results: Results, paths: Iterable[Path], recording: Any) -> dict[str, Any]:
    """The metadata describing `recording` with Sanket's findings as annotations: a SigMF
    recording's own, annotated, or a raw file's new one (`core:dataset` the file's name)."""
    meta_file = _meta_path(paths)
    if meta_file is not None:
        original = json.loads(meta_file.read_text(encoding="utf-8"))
        return meta_for(results, original=original)
    if isinstance(recording, RawRecording):
        return meta_for(results, dataset=recording.data_path.name)
    raise NotDescribable(
        f"{results.recording.container} is not a raw file or a SigMF recording, so there is no "
        "dataset a SigMF description could name"
    )


def save_beside(results: Results, recording: Any) -> Path:
    """Write `<stem>.sigmf-meta` next to the raw file `recording` reads, naming that file as its
    dataset, and return its path. Refuses a recording that isn't a raw file, and never overwrites
    a metadata file that is already there."""
    if not isinstance(recording, RawRecording):
        raise NotDescribable(
            f"{results.recording.container} is not a raw file: only raw samples can be saved as "
            "SigMF without copying them"
        )
    target = recording.data_path.with_suffix(".sigmf-meta")
    if target.exists():
        raise RecordingError(f"{target.name} already exists beside the file; not overwriting it")
    target.write_bytes(render_meta(meta_for(results, dataset=recording.data_path.name)).encode())
    return target
