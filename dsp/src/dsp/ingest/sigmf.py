"""Read SigMF metadata into evidence Parameters. Nothing missing is ever filled with a default."""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dsp.evidence import EvidenceLevel, Parameter
from dsp.ingest.formats import SampleFormat
from dsp.results import Assumptions

FORMAT_HINT = "Choose the sample format from the ranked format candidates."
RATE_HINT = (
    "Enter the sample rate. Until then, frequencies and rates are reported as fractions of it."
)
FREQUENCY_HINT = (
    "Enter the centre frequency. Until then, frequencies are relative to the recording's centre."
)


@dataclass(frozen=True)
class SigmfRecording:
    data_path: Path
    datatype: Parameter
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
            sample_rate=self.sample_rate,
            center_frequency=self.center_frequency,
            iq_order=_iq_order(self.sample_format),
        )


@dataclass(frozen=True)
class _Field:
    id: str
    name: str
    key: str
    hint: str

    def measured(
        self, value: str | float, *, unit: str | None = None, warnings: tuple[str, ...] = ()
    ) -> Parameter:
        return Parameter(
            id=self.id,
            name=self.name,
            method=f"{self.key} in SigMF metadata",
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
SAMPLE_RATE = _Field("sample_rate", "Sample rate", "core:sample_rate", RATE_HINT)
CENTER_FREQUENCY = _Field("center_frequency", "Centre frequency", "core:frequency", FREQUENCY_HINT)


def read_sigmf(meta_path: Path) -> SigmfRecording:
    meta: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))
    global_: dict[str, Any] = meta.get("global") or {}
    captures: list[dict[str, Any]] = meta.get("captures") or [{}]
    data_path = meta_path.with_suffix(".sigmf-data")
    return SigmfRecording(
        data_path=data_path,
        datatype=_datatype(global_.get(DATATYPE.key), data_path),
        sample_rate=_measurement(global_.get(SAMPLE_RATE.key), SAMPLE_RATE, "S/s"),
        center_frequency=_measurement(
            captures[0].get(CENTER_FREQUENCY.key), CENTER_FREQUENCY, "Hz", allow_zero=True
        ),
    )


def _datatype(raw: object, data_path: Path) -> Parameter:
    if not isinstance(raw, str):
        return DATATYPE.unknown(f"{DATATYPE.key} is missing from the SigMF metadata")
    try:
        fmt = SampleFormat.parse(raw)
    except ValueError as error:
        return DATATYPE.unknown(str(error))
    warnings: tuple[str, ...] = ()
    if data_path.exists() and (extra := data_path.stat().st_size % fmt.sample_bytes):
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


def _iq_order(fmt: SampleFormat | None) -> Parameter | None:
    method = "SigMF convention: the in-phase component is stored first"
    if fmt is None:
        return Parameter(
            id="iq_order",
            name="IQ order",
            value=None,
            level=EvidenceLevel.UNKNOWN,
            method=method,
            evidence=(
                "The sample format is unknown, so it isn't known whether samples are complex.",
            ),
            resolve_hint=FORMAT_HINT,
        )
    if not fmt.is_complex:
        return None
    return Parameter(
        id="iq_order",
        name="IQ order",
        value="IQ",
        level=EvidenceLevel.HYPOTHESIS,
        method=method,
        evidence=(
            "The samples can't confirm it: swapping I and Q only mirrors the spectrum. Toggle it "
            "if a known carrier sits on the wrong side.",
        ),
    )
