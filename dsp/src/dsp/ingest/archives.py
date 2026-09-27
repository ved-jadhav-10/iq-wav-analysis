"""`.gz` and `.zip` recordings, decompressed into the workspace before analysis.

Analysis needs random access, so a compressed recording is decompressed first. `unpacked_size`
reports what that will cost on disk before anything is written. `decompress` streams the data
out in chunks, and guards against hostile archives: member names that would escape the target
directory (absolute paths, drive letters, `..`), symbolic links, encrypted members, and
decompression bombs, stopped by an absolute byte limit and a compression-ratio limit, both
checked against the bytes actually produced rather than the sizes an archive claims.

Limits: a gzip file records its size modulo 4 GiB, so for larger files `unpacked_size` is a
lower bound and says so. Only the first member of a multi-member gzip stream is read.
"""

import gzip
import stat
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Protocol

CHUNK = 1 << 20
# Recordings of noise barely compress; zero-padded captures may reach tens or hundreds.
MAX_RATIO = 1000.0
# Deflate can't compress by more than about 1032:1, which bounds what a gzip ISIZE can hide.
_DEFLATE_MAX_RATIO = 1032


class _Readable(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...


class ArchiveError(ValueError):
    """The archive is unsafe, damaged or exceeds a limit; nothing partial is left behind."""


@dataclass(frozen=True)
class UnpackedSize:
    bytes: int
    exact: bool  # False when the format only gives a lower bound


def unpacked_size(path: Path) -> UnpackedSize:
    """What decompressing `path` will write, before writing it."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            return UnpackedSize(sum(i.file_size for i in z.infolist() if not i.is_dir()), True)
    with path.open("rb") as file:
        if file.read(2) != b"\x1f\x8b":
            raise ArchiveError(f"{path.name} is neither gzip nor zip")
        file.seek(-4, 2)
        isize = int.from_bytes(file.read(4), "little")
    # ISIZE is the size mod 2^32: exact only while the output can't have wrapped.
    return UnpackedSize(isize, path.stat().st_size * _DEFLATE_MAX_RATIO < 1 << 32)


def decompress(
    path: Path, target: Path, *, limit_bytes: int, max_ratio: float = MAX_RATIO
) -> tuple[Path, ...]:
    """Decompress a `.gz` file or every file in a `.zip` into `target`; return what was written."""
    target.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(path):
        return _unzip(path, target, limit_bytes, max_ratio)
    with path.open("rb") as file:
        if file.read(2) != b"\x1f\x8b":
            raise ArchiveError(f"{path.name} is neither gzip nor zip")
    name = path.name[:-3] if path.name.lower().endswith(".gz") else path.name + ".out"
    out = target / _safe_name(name)
    try:
        with gzip.open(path, "rb") as source:
            _copy(source, out, limit_bytes, path.stat().st_size, max_ratio, path.name)
    except (ArchiveError, OSError, EOFError, zlib.error) as error:
        out.unlink(missing_ok=True)
        if isinstance(error, ArchiveError):
            raise
        raise ArchiveError(f"{path.name} is damaged: {error}") from error
    return (out,)


def _unzip(path: Path, target: Path, limit: int, max_ratio: float) -> tuple[Path, ...]:
    written: list[Path] = []
    total = 0
    try:
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                if info.flag_bits & 0x1:
                    raise ArchiveError(f"{info.filename} is encrypted")
                if stat.S_ISLNK(info.external_attr >> 16):
                    raise ArchiveError(f"{info.filename} is a symbolic link")
                out = target / _safe_relative(info.filename)
                if not out.resolve().is_relative_to(target.resolve()):
                    raise ArchiveError(f"{info.filename} would be written outside the target")
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as source:
                    written.append(out)
                    total += _copy(
                        source,
                        out,
                        limit - total,
                        max(info.compress_size, 1),
                        max_ratio,
                        info.filename,
                    )
    except (ArchiveError, zipfile.BadZipFile, OSError, zlib.error) as error:
        for out in written:
            out.unlink(missing_ok=True)
        if isinstance(error, ArchiveError):
            raise
        raise ArchiveError(f"{path.name} is damaged: {error}") from error
    return tuple(written)


def _copy(
    source: _Readable, out: Path, limit: int, packed: int, max_ratio: float, name: str
) -> int:
    count = 0
    with out.open("wb") as sink:
        while chunk := source.read(CHUNK):
            count += len(chunk)
            if count > limit:
                raise ArchiveError(f"{name} unpacks to more than the {limit}-byte limit")
            if count > packed * max_ratio:
                raise ArchiveError(
                    f"{name} unpacks to over {max_ratio:g} times its compressed size: "
                    "refused as a possible decompression bomb"
                )
            sink.write(chunk)
    return count


def _safe_relative(name: str) -> Path:
    """A zip member name as a relative path, refusing anything that could climb out."""
    posix, windows = PurePosixPath(name.replace("\\", "/")), PureWindowsPath(name)
    if posix.is_absolute() or windows.drive or windows.root or ".." in posix.parts or not name:
        raise ArchiveError(f"unsafe member name {name!r}")
    return Path(*posix.parts)


def _safe_name(name: str) -> str:
    return _safe_relative(name).name
