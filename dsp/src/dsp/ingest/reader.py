from collections.abc import Iterator
from pathlib import Path
from typing import Any, Self

from numpy.typing import NDArray

from dsp.ingest.formats import SampleFormat

DEFAULT_CHUNK = 1 << 20


class SampleReader:
    """Random-access, chunked reads of a raw sample file; memory stays bounded by the chunk size.

    The samples run from `offset_bytes` for `length_bytes` bytes, or to the end of the file.
    """

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
        raw = self.fmt.components(self._file.read(count * self.fmt.sample_bytes))
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
