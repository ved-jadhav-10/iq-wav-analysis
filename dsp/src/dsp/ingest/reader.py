from collections.abc import Iterator
from pathlib import Path
from typing import Any, Self

import numpy as np
from numpy.typing import NDArray

from dsp.ingest.formats import SampleFormat

DEFAULT_CHUNK = 1 << 20


class SampleReader:
    """Random-access, chunked reads of a raw sample file; memory stays bounded by the chunk size."""

    def __init__(
        self, path: Path, fmt: SampleFormat, *, offset_bytes: int = 0, swap_iq: bool = False
    ) -> None:
        payload = path.stat().st_size - offset_bytes
        if offset_bytes < 0 or payload < 0:
            raise ValueError(f"offset {offset_bytes} is outside the file")
        self.fmt = fmt
        self.swap_iq = swap_iq
        self.num_samples, self.trailing_bytes = divmod(payload, fmt.sample_bytes)
        self._offset = offset_bytes
        self._file = path.open("rb")

    def read(self, start: int, count: int) -> NDArray[Any]:
        if start < 0 or count < 0:
            raise ValueError("start and count must be non-negative")
        count = max(0, min(count, self.num_samples - start))
        self._file.seek(self._offset + start * self.fmt.sample_bytes)
        raw = np.frombuffer(
            self._file.read(count * self.fmt.sample_bytes), self.fmt.component_dtype
        )
        return self.fmt.decode(raw, swap_iq=self.swap_iq)

    def chunks(self, size: int = DEFAULT_CHUNK) -> Iterator[NDArray[Any]]:
        for start in range(0, self.num_samples, size):
            yield self.read(start, size)

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
