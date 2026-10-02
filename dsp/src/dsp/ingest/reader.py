"""Chunked, random-access sample readers; every container exposes the same interface (PLAN §3).

A recording's samples are a sequence of byte segments in one sample format: a single region of
a file (raw, SigMF, WAV), a member of a tar archive, one region per SigMF capture, one per file
of a numbered sequence, or one per VITA 49 packet payload. Memory stays bounded by the chunk
size, plus 24 bytes per segment for the segment table.
"""

from collections import OrderedDict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Protocol, Self

import numpy as np
from numpy.typing import NDArray

from dsp.ingest.formats import SampleFormat

DEFAULT_CHUNK = 1 << 20
_OPEN_FILES = 8


class Reader(Protocol):
    """What every container's reader offers: a sample count and chunked random access."""

    num_samples: int

    def read(self, start: int, count: int) -> NDArray[Any]: ...

    def chunks(self, size: int = DEFAULT_CHUNK) -> Iterator[NDArray[Any]]: ...

    def close(self) -> None: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, *exc_info: object) -> None: ...


@dataclass(frozen=True)
class Segment:
    path: Path
    offset: int  # bytes
    length: int  # bytes


@dataclass(frozen=True, eq=False)
class SegmentTable:
    """Many segments as arrays, for containers with one segment per packet."""

    paths: tuple[Path, ...]
    file: NDArray[np.int32]  # index into paths
    offset: NDArray[np.int64]
    length: NDArray[np.int64]

    @classmethod
    def of(cls, segments: Sequence[Segment]) -> "SegmentTable":
        paths = tuple(sorted({s.path for s in segments}))
        index = {p: i for i, p in enumerate(paths)}
        return cls(
            paths,
            np.array([index[s.path] for s in segments], dtype=np.int32),
            np.array([s.offset for s in segments], dtype=np.int64),
            np.array([s.length for s in segments], dtype=np.int64),
        )

    def __len__(self) -> int:
        return len(self.offset)


class SegmentReader:
    """Reads samples laid out across byte segments, in order, as one stream.

    Each segment holds whole samples; bytes at a segment's end that don't form a whole sample
    are skipped and counted in `trailing_bytes`.
    """

    def __init__(
        self,
        segments: Sequence[Segment] | SegmentTable,
        fmt: SampleFormat,
        *,
        swap_iq: bool = False,
    ) -> None:
        table = segments if isinstance(segments, SegmentTable) else SegmentTable.of(segments)
        for i, path in enumerate(table.paths):
            size = path.stat().st_size
            mine = table.file == i
            if np.any(table.offset[mine] < 0) or np.any(table.length[mine] < 0):
                raise ValueError(f"a segment of {path.name} has a negative offset or length")
            if np.any(table.offset[mine] + table.length[mine] > size):
                raise ValueError(f"a segment overruns {path.name} ({size} bytes)")
        self.fmt = fmt
        self.swap_iq = swap_iq
        self._paths = table.paths
        self._file_of = table.file
        self._offset = table.offset
        counts = table.length // fmt.sample_bytes
        self._start = np.concatenate(([0], np.cumsum(counts))).astype(np.int64)
        self.num_samples = int(self._start[-1])
        self.trailing_bytes = int(np.sum(table.length % fmt.sample_bytes))
        self._files: OrderedDict[int, BinaryIO] = OrderedDict()

    def read(self, start: int, count: int) -> NDArray[Any]:
        """`read_raw` with every non-finite sample (NaN, ±inf: a float file's corrupt samples)
        replaced by 0, so no stage downstream has to survive them. The capture-quality stage reads
        the raw samples and reports how many there were."""
        x = self.read_raw(start, count)
        if x.dtype.kind in "fc":
            finite = np.isfinite(x)
            if not finite.all():
                x = np.where(finite, x, np.zeros((), x.dtype))
        return x

    def read_raw(self, start: int, count: int) -> NDArray[Any]:
        if start < 0 or count < 0:
            raise ValueError("start and count must be non-negative")
        end = min(start + count, self.num_samples)
        parts: list[bytes] = []
        size = self.fmt.sample_bytes
        k = int(np.searchsorted(self._start, start, side="right")) - 1
        position = start
        while position < end:
            first, last = int(self._start[k]), int(self._start[k + 1])
            take = min(end, last) - position
            if take > 0:
                file = self._file(int(self._file_of[k]))
                file.seek(int(self._offset[k]) + (position - first) * size)
                parts.append(file.read(take * size))
                position += take
            k += 1
        return self.fmt.decode(self.fmt.components(b"".join(parts)), swap_iq=self.swap_iq)

    def chunks(self, size: int = DEFAULT_CHUNK) -> Iterator[NDArray[Any]]:
        for start in range(0, self.num_samples, size):
            yield self.read(start, size)

    def _file(self, i: int) -> BinaryIO:
        if i in self._files:
            self._files.move_to_end(i)
            return self._files[i]
        if len(self._files) >= _OPEN_FILES:
            self._files.popitem(last=False)[1].close()
        self._files[i] = self._paths[i].open("rb")
        return self._files[i]

    def close(self) -> None:
        for file in self._files.values():
            file.close()
        self._files.clear()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


class SampleReader(SegmentReader):
    """One region of one file: from `offset_bytes` for `length_bytes` bytes, or to the end."""

    def __init__(
        self,
        path: Path,
        fmt: SampleFormat,
        *,
        offset_bytes: int = 0,
        length_bytes: int | None = None,
        swap_iq: bool = False,
    ) -> None:
        size = path.stat().st_size
        if offset_bytes < 0 or offset_bytes > size:
            raise ValueError(f"offset {offset_bytes} is outside the file")
        payload = size - offset_bytes
        if length_bytes is not None:
            if length_bytes < 0 or length_bytes > payload:
                raise ValueError(
                    f"{length_bytes} bytes from offset {offset_bytes} overrun the file"
                )
            payload = length_bytes
        super().__init__([Segment(path, offset_bytes, payload)], fmt, swap_iq=swap_iq)
