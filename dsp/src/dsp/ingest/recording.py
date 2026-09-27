"""A recording read from a container: where its samples are and what the container states.

Containers whose samples are plain byte segments in one format (NumPy `.npy`, SDRangel `.sdriq`,
MIDAS Blue, VITA 49, numbered file sequences) share this type; each module only parses its
header into Parameters.
"""

from dataclasses import dataclass

from dsp.evidence import EvidenceLevel, Parameter
from dsp.ingest.assumptions import iq_order
from dsp.ingest.formats import SampleFormat
from dsp.ingest.reader import Segment, SegmentReader, SegmentTable
from dsp.results import Assumptions

NAMES = {
    "datatype": "Sample format",
    "data_offset": "Data offset",
    "sample_rate": "Sample rate",
    "center_frequency": "Centre frequency",
    "start_time": "Start time",
}
UNITS = {"data_offset": "B", "sample_rate": "S/s", "center_frequency": "Hz"}


def stated(
    id_: str,
    value: str | float,
    method: str,
    *,
    level: EvidenceLevel = EvidenceLevel.MEASURED,
    evidence: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    convention: str | None = None,
) -> Parameter:
    """A value the container states: MEASURED, or HYPOTHESIS when suspect or conventional."""
    return Parameter(
        id=id_,
        name=NAMES[id_],
        value=value,
        unit=UNITS.get(id_),
        level=level,
        method=method,
        evidence=evidence,
        warnings=warnings,
        convention=convention,
    )


def unknown(id_: str, method: str, why: str, hint: str) -> Parameter:
    return Parameter(
        id=id_,
        name=NAMES[id_],
        value=None,
        unit=UNITS.get(id_),
        level=EvidenceLevel.UNKNOWN,
        method=method,
        evidence=(why,),
        resolve_hint=hint,
    )


@dataclass(frozen=True)
class Recording:
    name: str
    segments: tuple[Segment, ...] | SegmentTable
    datatype: Parameter
    data_offset: Parameter
    sample_rate: Parameter
    center_frequency: Parameter
    iq_method: str  # what says I comes first
    iq_convention: str | None = None  # set when only a convention says so
    start_time: Parameter | None = None

    @property
    def sample_format(self) -> SampleFormat | None:
        value = self.datatype.value
        return SampleFormat.parse(value) if isinstance(value, str) else None

    def reader(self, *, swap_iq: bool = False) -> SegmentReader:
        fmt = self.sample_format
        if fmt is None:
            raise ValueError("the sample format is UNKNOWN; settle it before reading samples")
        return SegmentReader(self.segments, fmt, swap_iq=swap_iq)

    @property
    def assumptions(self) -> Assumptions:
        return Assumptions(
            datatype=self.datatype,
            data_offset=self.data_offset,
            sample_rate=self.sample_rate,
            center_frequency=self.center_frequency,
            iq_order=iq_order(self.sample_format, self.iq_method, convention=self.iq_convention),
        )


def clamp(offset: int, stated_bytes: int, size: int, what: str) -> tuple[int, tuple[str, ...]]:
    """The bytes actually present, with a warning when the header claims more."""
    available = max(0, size - offset)
    if stated_bytes <= available:
        return stated_bytes, ()
    return available, (
        f"The {what} states {stated_bytes} bytes of samples but the file holds only "
        f"{available}: the recording is truncated, and only the bytes present are read.",
    )
