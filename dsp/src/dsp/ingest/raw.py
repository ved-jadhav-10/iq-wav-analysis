"""Raw sample files with no metadata: the format is sniffed and every layout fact is stated."""

from dataclasses import dataclass
from pathlib import Path

from dsp.evidence import EvidenceLevel, Parameter
from dsp.ingest.assumptions import iq_order
from dsp.ingest.formats import SampleFormat
from dsp.ingest.rate import (
    RateCandidate,
    center_frequency_parameter,
    rate_candidates,
    sample_rate_parameter,
)
from dsp.ingest.reader import SampleReader
from dsp.ingest.recording import entered
from dsp.ingest.sniff import FormatSniff, sniff
from dsp.results import Assumptions


@dataclass(frozen=True)
class RawRecording:
    data_path: Path
    format_sniff: FormatSniff
    entered_datatype: str | None = None  # the analyst's choice, which replaces the sniffer's

    @property
    def datatype(self) -> Parameter:
        if self.entered_datatype is not None:
            return entered("datatype", self.entered_datatype, prior=self.format_sniff.datatype)
        return self.format_sniff.datatype

    @property
    def sample_format(self) -> SampleFormat | None:
        value = self.datatype.value
        return SampleFormat.parse(value) if isinstance(value, str) else None

    def reader(self, *, swap_iq: bool = False, datatype: str | None = None) -> SampleReader:
        """Samples from byte 0, as the proposed format or as `datatype` (another reading)."""
        fmt = SampleFormat.parse(datatype) if datatype else self.sample_format
        if fmt is None:
            raise ValueError("the sample format is UNKNOWN; settle it before reading samples")
        return SampleReader(self.data_path, fmt, swap_iq=swap_iq)

    @property
    def rate_candidates(self) -> tuple[RateCandidate, ...]:
        """Ranked sample-rate candidates; `rate.structural_test` can promote one."""
        fmt = self.sample_format
        return rate_candidates(self.data_path.name, fmt.datatype if fmt else None)

    @property
    def assumptions(self) -> Assumptions:
        fmt = self.sample_format
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
            sample_rate=sample_rate_parameter(
                self.rate_candidates,
                fmt.datatype if fmt else None,
                "Sample-rate candidates: file name and standard SDR device rates",
                "A raw file doesn't record its sample rate.",
            ),
            center_frequency=center_frequency_parameter(
                self.data_path.name,
                "Centre-frequency candidates: file name",
                "A raw file doesn't record its centre frequency.",
            ),
            iq_order=iq_order(
                fmt,
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
