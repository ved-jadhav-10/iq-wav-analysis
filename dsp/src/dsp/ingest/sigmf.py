"""Read SigMF recordings into evidence Parameters. Nothing missing is ever filled with a default.

Covers a `.sigmf-meta` with its `.sigmf-data`; a Non-Conforming Dataset named by `core:dataset`,
with `core:header_bytes` skipped at each capture and `core:trailing_bytes` at the end; several
captures in one dataset; and `.sigmf` archives, read in place from the tar without extracting.

Limits: a dataset with more than one interleaved channel (`core:num_channels`) is reported
UNKNOWN rather than split. A recording whose captures change centre frequency reports the
first capture's, with a warning naming the others. Compressed archives are decompressed first.
"""

import json
import math
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

from dsp.evidence import EvidenceLevel, Parameter, revise
from dsp.ingest.assumptions import (
    FORMAT_HINT,
    FREQUENCY_HINT,
    OFFSET_HINT,
    RATE_HINT,
    iq_order,
)
from dsp.ingest.formats import SampleFormat
from dsp.ingest.reader import Segment, SegmentReader
from dsp.results import Assumptions

# A metadata file is JSON text; anything larger isn't one worth loading.
MAX_META_BYTES = 64 << 20


@dataclass(frozen=True)
class SigmfRecording:
    name: str  # the metadata file's name (inside the archive, for an archive)
    data_path: Path  # the file holding the samples: the dataset, or the archive
    segments: tuple[Segment, ...]  # empty when the samples can't be located
    datatype: Parameter
    data_offset: Parameter
    sample_rate: Parameter
    center_frequency: Parameter

    @property
    def sample_format(self) -> SampleFormat | None:
        value = self.datatype.value
        return SampleFormat.parse(value) if isinstance(value, str) else None

    def reader(self, *, swap_iq: bool = False) -> SegmentReader:
        fmt = self.sample_format
        if fmt is None:
            raise ValueError("the sample format is UNKNOWN; settle it before reading samples")
        if not self.segments:
            raise ValueError(f"the samples of {self.name} can't be located")
        return SegmentReader(self.segments, fmt, swap_iq=swap_iq)

    @property
    def assumptions(self) -> Assumptions:
        return Assumptions(
            datatype=self.datatype,
            data_offset=self.data_offset,
            sample_rate=self.sample_rate,
            center_frequency=self.center_frequency,
            iq_order=iq_order(
                self.sample_format, "SigMF specification: the in-phase component is stored first"
            ),
        )


@dataclass(frozen=True)
class _Field:
    id: str
    name: str
    key: str
    hint: str

    def measured(
        self,
        value: str | float,
        *,
        unit: str | None = None,
        method: str | None = None,
        evidence: tuple[str, ...] = (),
        warnings: tuple[str, ...] = (),
    ) -> Parameter:
        return Parameter(
            id=self.id,
            name=self.name,
            method=method or f"{self.key} in SigMF metadata",
            value=value,
            unit=unit,
            level=EvidenceLevel.MEASURED,
            evidence=evidence,
            warnings=warnings,
        )

    def unknown(self, reason: str) -> Parameter:
        return Parameter(
            id=self.id,
            name=self.name,
            method=f"{self.key} in SigMF metadata",
            value=None,
            level=EvidenceLevel.UNKNOWN,
            evidence=(reason,),
            resolve_hint=self.hint,
        )


DATATYPE = _Field("datatype", "Sample format", "core:datatype", FORMAT_HINT)
DATA_OFFSET = _Field("data_offset", "Data offset", "core:header_bytes", OFFSET_HINT)
SAMPLE_RATE = _Field("sample_rate", "Sample rate", "core:sample_rate", RATE_HINT)
CENTER_FREQUENCY = _Field("center_frequency", "Centre frequency", "core:frequency", FREQUENCY_HINT)


@dataclass(frozen=True)
class _Dataset:
    path: Path  # the file the bytes are in
    base: int  # where the dataset starts in it
    size: int  # dataset length in bytes


def read_sigmf(meta_path: Path) -> SigmfRecording:
    """A recording from a `.sigmf-meta` file and the dataset beside it."""
    meta = _load(meta_path.read_bytes(), meta_path.name)
    global_ = _object(meta.get("global"))
    dataset_name = global_.get("core:dataset")
    if dataset_name is not None:
        data_path = meta_path.parent / _plain_name(dataset_name)
    else:
        data_path = meta_path.with_suffix(".sigmf-data")
    dataset = _Dataset(data_path, 0, data_path.stat().st_size) if data_path.exists() else None
    return _recording(meta, meta_path.name, data_path, dataset)


def read_sigmf_archive(path: Path) -> tuple[SigmfRecording, ...]:
    """Every recording in a `.sigmf` archive (an uncompressed POSIX tar), read in place."""
    try:
        with tarfile.open(path, "r:") as tar:
            recordings = _archive(tar, path)
    except tarfile.ReadError as error:
        raise ValueError(f"{path.name} is not an uncompressed tar archive: {error}") from error
    if not recordings:
        raise ValueError(f"{path.name} holds no SigMF recording")
    return recordings


def _archive(tar: tarfile.TarFile, path: Path) -> tuple[SigmfRecording, ...]:
    members = {m.name: m for m in tar.getmembers() if m.isreg() and not m.issparse()}
    recordings: list[SigmfRecording] = []
    for name, member in sorted(members.items()):
        if not name.endswith(".sigmf-meta"):
            continue
        if member.size > MAX_META_BYTES:
            raise ValueError(f"{name} is too large to be SigMF metadata")
        extracted = tar.extractfile(member)
        assert extracted is not None  # a regular member
        meta = _load(extracted.read(), name)
        dataset_name = _object(meta.get("global")).get("core:dataset")
        meta_path = PurePosixPath(name)
        data_name = str(
            meta_path.parent / _plain_name(dataset_name)
            if dataset_name is not None
            else meta_path.with_suffix(".sigmf-data")
        )
        data = members.get(data_name)
        dataset = _Dataset(path, data.offset_data, data.size) if data else None
        recordings.append(_recording(meta, name, path, dataset))
    return tuple(recordings)


def _recording(
    meta: dict[str, Any], name: str, data_path: Path, dataset: _Dataset | None
) -> SigmfRecording:
    global_ = _object(meta.get("global"))
    if global_.get("core:metadata_only") is True:
        raise ValueError(f"{name} is metadata only: it describes no samples")
    raw_captures = meta.get("captures")
    captures = (
        [_object(c) for c in cast(list[Any], raw_captures)]
        if isinstance(raw_captures, list)
        else []
    )
    captures = captures or [{}]
    datatype = _datatype(global_.get(DATATYPE.key), global_.get("core:num_channels"))
    fmt = SampleFormat.parse(datatype.value) if isinstance(datatype.value, str) else None
    trailing = global_.get("core:trailing_bytes", 0)
    layout = _layout(captures, trailing, fmt, dataset)
    if isinstance(layout, str):
        data_offset, segments = DATA_OFFSET.unknown(layout), ()
    else:
        data_offset, segments = layout
    if fmt is not None and segments:
        extra = sum(s.length % fmt.sample_bytes for s in segments)
        if extra:
            datatype = revise(
                datatype,
                warnings=(
                    f"The data ends with {extra} byte(s) that don't form a whole "
                    f"{fmt.datatype} sample; the datatype may be wrong or the file truncated.",
                ),
            )
    return SigmfRecording(
        name=name,
        data_path=data_path,
        segments=segments,
        datatype=datatype,
        data_offset=data_offset,
        sample_rate=_measurement(global_.get(SAMPLE_RATE.key), SAMPLE_RATE, "S/s"),
        center_frequency=_center_frequency(captures),
    )


def _layout(
    captures: list[dict[str, Any]],
    trailing: object,
    fmt: SampleFormat | None,
    dataset: _Dataset | None,
) -> tuple[Parameter, tuple[Segment, ...]] | str:
    """The data offset and the byte segments of each capture, or why they can't be found."""
    starts: list[int] = []
    headers: list[int] = []
    for c in captures:
        start, header = c.get("core:sample_start", 0), c.get(DATA_OFFSET.key, 0)
        if not _count(start):
            return f"core:sample_start has an invalid value: {start!r}"
        if not _count(header):
            return f"{DATA_OFFSET.key} has an invalid value: {header!r}"
        starts.append(cast(int, start))
        headers.append(cast(int, header))
    if not _count(trailing):
        return f"core:trailing_bytes has an invalid value: {trailing!r}"
    if starts != sorted(starts):
        return "The captures' core:sample_start values are out of order."
    if "core:header_bytes" in captures[0]:
        offset = DATA_OFFSET.measured(headers[0], unit="B")
    else:
        offset = DATA_OFFSET.measured(
            0,
            unit="B",
            method="SigMF: a dataset file starts with its first sample unless "
            "core:header_bytes says otherwise",
        )
    if fmt is None or dataset is None:
        return offset, ()
    end = dataset.base + dataset.size - cast(int, trailing)
    segments: list[Segment] = []
    skipped = 0
    for i, (start, header) in enumerate(zip(starts, headers, strict=True)):
        skipped += header
        at = dataset.base + skipped + start * fmt.sample_bytes
        stop = (
            dataset.base + skipped + starts[i + 1] * fmt.sample_bytes
            if i + 1 < len(starts)
            else end
        )
        if at > end or stop > end or stop < at:
            return f"Capture {i} (sample {start}, {header} header bytes) lies outside the dataset."
        segments.append(Segment(dataset.path, at, stop - at))
    if len(segments) > 1 and not any(headers[1:]):
        segments = [Segment(dataset.path, segments[0].offset, end - segments[0].offset)]
    return offset, tuple(segments)


def _datatype(raw: object, channels: object) -> Parameter:
    if not isinstance(raw, str):
        return DATATYPE.unknown(f"{DATATYPE.key} is missing from the SigMF metadata")
    try:
        fmt = SampleFormat.parse(raw)
    except ValueError as error:
        return DATATYPE.unknown(str(error))
    if not fmt.is_sigmf:
        return DATATYPE.unknown(f"{raw!r} is not a SigMF core:datatype")
    if channels not in (None, 1):
        return Parameter(
            id="datatype",
            name="Sample format",
            value=None,
            level=EvidenceLevel.UNKNOWN,
            method="core:num_channels in SigMF metadata",
            evidence=(f"The dataset interleaves {channels!r} channels of {fmt.datatype}.",),
            resolve_hint="Extract one channel into its own recording; Sanket reads one channel.",
        )
    return DATATYPE.measured(fmt.datatype)


def _center_frequency(captures: list[dict[str, Any]]) -> Parameter:
    first = _measurement(
        captures[0].get(CENTER_FREQUENCY.key), CENTER_FREQUENCY, "Hz", allow_zero=True
    )
    changes = [
        f"capture {i} (from sample {c.get('core:sample_start')}) is at {c[CENTER_FREQUENCY.key]} Hz"
        for i, c in enumerate(captures[1:], start=1)
        if c.get(CENTER_FREQUENCY.key, first.value) != first.value
    ]
    if not changes or first.value is None:
        return first
    return revise(
        first,
        warnings=(
            "The centre frequency changes between captures; this is the first capture's. "
            + "; ".join(changes)
            + ".",
        ),
    )


def _measurement(raw: object, field: _Field, unit: str, *, allow_zero: bool = False) -> Parameter:
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        return field.unknown(f"{field.key} is missing from the SigMF metadata")
    value = float(raw)
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        return field.unknown(f"{field.key} has an invalid value: {raw!r}")
    return field.measured(value, unit=unit)


def _load(data: bytes, name: str) -> dict[str, Any]:
    try:
        meta = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{name} is not valid SigMF metadata (UTF-8 JSON): {error}") from error
    if not isinstance(meta, dict):
        raise ValueError(f"{name} is not valid SigMF metadata: the top level isn't an object")
    return cast(dict[str, Any], meta)


def _object(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _plain_name(value: object) -> str:
    """core:dataset is a bare file name in the metadata's directory, never a path."""
    if (
        not isinstance(value, str)
        or not value
        or value in (".", "..")
        or any(c in value for c in "/\\:\0")
    ):
        raise ValueError(f"core:dataset must be a plain file name, not {value!r}")
    return value
