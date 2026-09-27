"""Read SigMF metadata into evidence Parameters. Nothing missing is ever filled with a default."""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dsp.evidence import EvidenceLevel, Parameter
from dsp.ingest.assumptions import (
    FORMAT_HINT,
    FREQUENCY_HINT,
    OFFSET_HINT,
    RATE_HINT,
    iq_order,
)
from dsp.ingest.formats import SampleFormat
from dsp.results import Assumptions


@dataclass(frozen=True)
class SigmfRecording:
    data_path: Path
    datatype: Parameter
    data_offset: Parameter
    sample_rate: Parameter
    center_frequency: Parameter

    @property
    def sample_format(self) -> SampleFormat | None:
        value = self.datatype.value
        return SampleFormat.parse(value) if isinstance(value, str) else None

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
        warnings: tuple[str, ...] = (),
    ) -> Parameter:
        return Parameter(
            id=self.id,
            name=self.name,
            method=method or f"{self.key} in SigMF metadata",
            value=value,
            unit=unit,
            level=EvidenceLevel.MEASURED,
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


def read_sigmf(meta_path: Path) -> SigmfRecording:
    meta: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))
    global_: dict[str, Any] = meta.get("global") or {}
    captures: list[dict[str, Any]] = meta.get("captures") or [{}]
    data_path = meta_path.with_suffix(".sigmf-data")
    data_offset = _data_offset(captures[0])
    header = data_offset.value if isinstance(data_offset.value, int) else 0
    return SigmfRecording(
        data_path=data_path,
        datatype=_datatype(global_.get(DATATYPE.key), data_path, header),
        data_offset=data_offset,
        sample_rate=_measurement(global_.get(SAMPLE_RATE.key), SAMPLE_RATE, "S/s"),
        center_frequency=_measurement(
            captures[0].get(CENTER_FREQUENCY.key), CENTER_FREQUENCY, "Hz", allow_zero=True
        ),
    )


def _data_offset(capture: dict[str, Any]) -> Parameter:
    raw = capture.get(DATA_OFFSET.key)
    if raw is None:
        return DATA_OFFSET.measured(
            0,
            unit="B",
            method="SigMF: a dataset file starts with its first sample unless "
            "core:header_bytes says otherwise",
        )
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        return DATA_OFFSET.unknown(f"{DATA_OFFSET.key} has an invalid value: {raw!r}")
    return DATA_OFFSET.measured(raw, unit="B")


def _datatype(raw: object, data_path: Path, header: int) -> Parameter:
    if not isinstance(raw, str):
        return DATATYPE.unknown(f"{DATATYPE.key} is missing from the SigMF metadata")
    try:
        fmt = SampleFormat.parse(raw)
    except ValueError as error:
        return DATATYPE.unknown(str(error))
    warnings: tuple[str, ...] = ()
    if data_path.exists() and (extra := (data_path.stat().st_size - header) % fmt.sample_bytes):
        warnings = (
            f"The data file ends with {extra} byte(s) that don't form a whole {fmt.datatype} "
            "sample; the datatype may be wrong or the file truncated.",
        )
    return DATATYPE.measured(fmt.datatype, warnings=warnings)


def _measurement(raw: object, field: _Field, unit: str, *, allow_zero: bool = False) -> Parameter:
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        return field.unknown(f"{field.key} is missing from the SigMF metadata")
    value = float(raw)
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        return field.unknown(f"{field.key} has an invalid value: {raw!r}")
    return field.measured(value, unit=unit)
