"""Receiving a recording from the browser (PLAN §5 M7, "Every input route").

A recording is one or more files (a SigMF pair, a WAV, a raw file), so an upload is a *batch*: the
client picks a batch id, sends each file to it with its own streamed PUT, then opens the main file
by the path the last PUT returned. Nothing is buffered whole in memory, and the file never leaves
the machine: it lands in the workspace directory.

Everything a client controls is checked here: the batch id is 32 hex digits, the file name is a
plain name (no separators, no dot-files, nothing Windows would treat as a device), the size is
capped while the bytes arrive rather than trusted from a header, and a name can't be sent twice.
"""

import re
from collections.abc import AsyncIterator
from pathlib import Path

import anyio.to_thread

DEFAULT_MAX_UPLOAD_BYTES = 16 * 1024**3

_BATCH = re.compile(r"[0-9a-f]{32}")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ +()-]{0,199}")
_WINDOWS_DEVICES = frozenset(
    {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))}
)


class UploadError(ValueError):
    """An upload was refused; `status` is the HTTP status that says why."""

    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


def check_name(name: str) -> str:
    """The name if it is safe to create as a file, else `UploadError`."""
    if (
        not _NAME.fullmatch(name)
        or name.endswith((".", " "))
        or name.split(".")[0].strip().lower() in _WINDOWS_DEVICES
    ):
        raise UploadError(
            "file names may hold letters, digits, spaces and . _ + ( ) -, start with a letter or "
            "digit, and be at most 200 characters"
        )
    return name


class UploadStore:
    def __init__(self, workspace: Path, max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES) -> None:
        self.root = workspace / "uploads"
        self.max_bytes = max_bytes

    def batch_dir(self, batch: str) -> Path:
        if not _BATCH.fullmatch(batch):
            raise UploadError("the batch id must be 32 lowercase hex digits")
        return self.root / batch

    async def save(
        self, batch: str, name: str, chunks: AsyncIterator[bytes], declared: int | None
    ) -> Path:
        """Stream `chunks` to `<workspace>/uploads/<batch>/<name>` and return that path."""
        directory = self.batch_dir(batch)
        target = directory / check_name(name)
        if declared is not None and declared > self.max_bytes:
            raise UploadError(f"the file is larger than the {self.max_bytes} byte limit", 413)
        directory.mkdir(parents=True, exist_ok=True)
        try:
            handle = target.open("xb")  # exclusive: a name can't be sent twice
        except FileExistsError:
            raise UploadError(f"{name} was already uploaded in this batch", 409) from None
        written = 0
        try:
            with handle:
                async for chunk in chunks:
                    written += len(chunk)
                    if written > self.max_bytes:
                        raise UploadError(
                            f"the file is larger than the {self.max_bytes} byte limit", 413
                        )
                    await anyio.to_thread.run_sync(handle.write, chunk)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        if written == 0:
            target.unlink()
            raise UploadError("the file is empty")
        return target
