"""Raw sample files with no metadata: the format is sniffed and every layout fact is stated."""

from dataclasses import dataclass
from pathlib import Path

from dsp.evidence import EvidenceLevel, Parameter
from dsp.ingest.assumptions import FREQUENCY_HINT, RATE_HINT, iq_order
from dsp.ingest.formats import SampleFormat
from dsp.ingest.sniff import FormatSniff, sniff
from dsp.results import Assumptions

_NO_METADATA = "Raw file: no metadata"


@dataclass(frozen=True)
class RawRecording:
    data_path: Path
    format_sniff: FormatSniff

    @property
    def datatype(self) -> Parameter:
        return self.format_sniff.datatype

    @property
    def sample_format(self) -> SampleFormat | None:
        value = self.datatype.value
        return SampleFormat.parse(value) if isinstance(value, str) else None

    @property
    def assumptions(self) -> Assumptions:
        return Assumptions(
            datatype=self.datatype,
            data_offset=Parameter(
                id="data_offset",
                name="Data offset",
                value=0,
                unit="B",
                level=EvidenceLevel.HYPOTHESIS,
                method="No container header recognised",
                evidence=(
                    "No known container header was found at the start of the file, so the "
                    "samples are assumed to start at byte 0.",
                ),
                convention="A raw file is taken to have no header. If the recording tool wrote "
                "one, enter its length.",
            ),
            sample_rate=_unknown("sample_rate", "Sample rate", RATE_HINT),
            center_frequency=_unknown("center_frequency", "Centre frequency", FREQUENCY_HINT),
            iq_order=iq_order(
                self.sample_format,
                "Convention for raw I/Q recordings: the in-phase component is stored first",
                convention="Most SDR tools store I before Q, but a raw file doesn't say. Swap if a "
                "known carrier sits on the wrong side of the spectrum.",
            ),
        )


def read_raw(path: Path) -> RawRecording:
    result = sniff(path)
    if result.container is not None:
        raise ValueError(f"{path.name} is a {result.container.upper()} file, not raw samples")
    return RawRecording(path, result)


def _unknown(id_: str, name: str, hint: str) -> Parameter:
    return Parameter(
        id=id_,
        name=name,
        value=None,
        level=EvidenceLevel.UNKNOWN,
        method=_NO_METADATA,
        evidence=(f"A raw file doesn't record its {name.lower()}.",),
        resolve_hint=hint,
    )
